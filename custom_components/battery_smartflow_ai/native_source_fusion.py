"""Fuse independently normalized Zendure telemetry with source provenance."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from .core.models import (
    MeasuredValue,
    NeutralDeviceState,
    NeutralPackState,
    ReportedDeviceSetpoints,
    ZendureTransport,
)
from .native_read_source import (
    NativeReadSourceArbiter,
    SelectedMeasurement,
    SourceMeasurement,
)
from .zendure_cloud import ZendureCloudBootstrap
from .zendure_cloud_mqtt import CloudMqttMessage
from .zendure_hems_activity import HemsActivityDiagnostic
from .zendure_normalizer import (
    MAIN_PROPERTY_MAPPINGS,
    PACK_PROPERTY_MAPPINGS,
    NormalizationResult,
    ZendureCloudNormalizer,
)


_TRANSPORTS = (
    ZendureTransport.ZENSDK,
    ZendureTransport.LOCAL_MQTT,
    ZendureTransport.CLOUD_MQTT,
)
_SAFETY_PROPERTIES = frozenset(
    {
        "hems_active",
        "fault_code",
        "protection_active",
        "mode",
        "soc_pct",
        "cell_min_v",
        "cell_max_v",
        "temperature_c",
    }
)
_SAFETY_TOLERANCES = {
    "soc_pct": 5.0,
    "cell_min_v": 0.15,
    "cell_max_v": 0.15,
    "temperature_c": 10.0,
}


class NativeSourceFusion:
    """Keep transport histories separate and fuse only neutral snapshots."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        *,
        preferred_transport: ZendureTransport | None = None,
    ) -> None:
        self._normalizers = {
            transport: ZendureCloudNormalizer(bootstrap) for transport in _TRANSPORTS
        }
        for item in bootstrap.devices:
            system_id = item.candidate.candidate_id
            self._normalizers[ZendureTransport.ZENSDK].set_online(system_id, None)
            self._normalizers[ZendureTransport.LOCAL_MQTT].set_online(
                system_id, None
            )
        priority = (
            (preferred_transport,)
            + tuple(item for item in _TRANSPORTS if item is not preferred_transport)
            if preferred_transport is not None
            else _TRANSPORTS
        )
        self._arbiter = NativeReadSourceArbiter(default_priority=priority)
        self._selection: dict[str, dict[str, SelectedMeasurement[Any]]] = {}
        self._selection_changed_at: dict[str, dict[str, datetime]] = {}
        self._retained_main: dict[
            tuple[ZendureTransport, str], dict[str, bool]
        ] = {}
        self._retained_packs: dict[
            tuple[ZendureTransport, str, str], dict[str, bool]
        ] = {}

    def apply(
        self, message: CloudMqttMessage, *, now: datetime | None = None
    ) -> NormalizationResult | None:
        transport = _transport(message.transport)
        if transport is None:
            return None
        result = self._normalizers[transport].apply(message, now=now)
        if result is None or message.device_candidate_id is None:
            return None
        self._record_retained(transport, message)
        return self.snapshot(
            message.device_candidate_id,
            now=now or message.received_at,
        )

    def snapshot(
        self, system_id: str, *, now: datetime | None = None
    ) -> NormalizationResult:
        results = {
            transport: normalizer.snapshot(system_id, now=now)
            for transport, normalizer in self._normalizers.items()
        }
        states = {transport: result.state for transport, result in results.items()}
        trace: dict[str, SelectedMeasurement[Any]] = {}
        current = now or datetime.now(timezone.utc)

        def select(
            name: str,
            values: dict[ZendureTransport, MeasuredValue[Any]],
            retained: dict[ZendureTransport, bool] | None = None,
        ):
            target = name.rsplit(".", 1)[-1]
            selected = self._arbiter.select(
                name,
                tuple(
                    SourceMeasurement(
                        source,
                        value,
                        (retained or {}).get(source, False),
                    )
                    for source, value in values.items()
                ),
                safety_critical=target in _SAFETY_PROPERTIES,
                conflict_tolerance=_SAFETY_TOLERANCES.get(target),
            )
            trace[name] = selected
            previous = self._selection.get(system_id, {}).get(name)
            if previous is None or previous.transport != selected.transport:
                self._selection_changed_at.setdefault(system_id, {})[name] = current
            return selected.measurement

        scalar_names = (
            "firmware",
            "online",
            "soc_pct",
            "charge_power_w",
            "discharge_power_w",
            "ac_input_power_w",
            "ac_output_power_w",
            "pv_power_w",
            "mode",
            "hems_active",
            "fault_code",
            "protection_active",
            "heating_active",
            "temperature_c",
            "battery_voltage_v",
            "offgrid_power_w",
        )
        selected_values = {
            name: select(
                name,
                {
                    source: getattr(state, name)
                    for source, state in states.items()
                },
                {
                    source: self._retained_main.get((source, system_id), {}).get(
                        name, False
                    )
                    for source in states
                },
            )
            for name in scalar_names
        }
        setpoints = ReportedDeviceSetpoints(
            **{
                item.name: select(
                    f"setpoints.{item.name}",
                    {
                        source: getattr(state.setpoints, item.name)
                        for source, state in states.items()
                    },
                    {
                        source: self._retained_main.get(
                            (source, system_id), {}
                        ).get(item.name, False)
                        for source in states
                    },
                )
                for item in fields(ReportedDeviceSetpoints)
            }
        )
        packs = self._fuse_packs(system_id, states, select)
        preferred = trace["soc_pct"].transport
        if preferred is None:
            preferred = max(
                states,
                key=lambda source: states[source].last_message_at
                or datetime.min.replace(tzinfo=(now.tzinfo if now else None)),
            )
        exemplar = states[preferred]
        state = NeutralDeviceState(
            system_id=system_id,
            observed_transport=preferred,
            model=exemplar.model,
            setpoints=setpoints,
            last_message_at=max(
                (
                    item.last_message_at
                    for item in states.values()
                    if item.last_message_at
                ),
                default=None,
            ),
            packs=packs,
            diagnostics={
                name: select(
                    f"diagnostics.{name}",
                    {source: item.diagnostics[name] for source, item in states.items() if name in item.diagnostics},
                    {source: self._retained_main.get((source, system_id), {}).get(name, False) for source in states},
                ) for name in sorted({key for item in states.values() for key in item.diagnostics})
            },
            **selected_values,
        )
        self._selection[system_id] = trace
        return NormalizationResult(
            state,
            tuple(
                sorted(
                    {
                        name
                        for result in results.values()
                        for name in result.unknown_main_properties
                    }
                )
            ),
            tuple(
                sorted(
                    {
                        name
                        for result in results.values()
                        for name in result.unknown_pack_properties
                    }
                )
            ),
        )

    def _fuse_packs(self, system_id, states, select):
        by_source = {
            source: {pack.pack_id: pack for pack in state.packs}
            for source, state in states.items()
        }
        pack_ids = sorted(
            {pack_id for packs in by_source.values() for pack_id in packs}
        )
        result = []
        measurement_names = tuple(
            item.name
            for item in fields(NeutralPackState)
            if item.name
            not in {
                "pack_id",
                "parent_system_id",
                "serial_number",
                "last_message_at",
            }
        )
        for pack_id in pack_ids:
            available = {
                source: packs[pack_id]
                for source, packs in by_source.items()
                if pack_id in packs
            }
            values = {
                name: select(
                    f"packs.{pack_id}.{name}",
                    {
                        source: getattr(pack, name)
                        for source, pack in available.items()
                    },
                    {
                        source: self._retained_packs.get(
                            (source, system_id, pack_id), {}
                        ).get(name, False)
                        for source in available
                    },
                )
                for name in measurement_names
            }
            serial = next(
                (
                    available[source].serial_number
                    for source in _TRANSPORTS
                    if source in available and available[source].serial_number
                ),
                None,
            )
            result.append(
                NeutralPackState(
                    pack_id=pack_id,
                    parent_system_id=system_id,
                    serial_number=serial,
                    last_message_at=max(
                        (
                            pack.last_message_at
                            for pack in available.values()
                            if pack.last_message_at
                        ),
                        default=None,
                    ),
                    **values,
                )
            )
        return tuple(result)

    def set_online(
        self,
        system_id: str,
        online: bool | None,
        *,
        transport: ZendureTransport | None = None,
    ) -> None:
        targets = (transport,) if transport is not None else _TRANSPORTS
        for source in targets:
            self._normalizers[source].set_online(system_id, online)

    def set_hems_monitoring(
        self, system_id: str, available: bool, *, observed_at: datetime
    ) -> None:
        for source in (ZendureTransport.CLOUD_MQTT, ZendureTransport.LOCAL_MQTT):
            self._normalizers[source].set_hems_monitoring(
                system_id, available, observed_at=observed_at
            )

    def hems_diagnostics(
        self,
        system_id: str,
        *,
        now: datetime,
    ) -> HemsActivityDiagnostic:
        values = [
            self._normalizers[source].hems_diagnostics(system_id, now=now)
            for source in (ZendureTransport.CLOUD_MQTT, ZendureTransport.LOCAL_MQTT)
        ]
        return next((value for value in values if value.monitoring), values[0])

    def source_diagnostics(
        self,
        system_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        return {
            name: {
                "transport": selected.transport.value if selected.transport else None,
                "status": selected.status.value,
                "reason": selected.reason,
                "alternatives": [source.value for source in selected.alternatives],
                "selected_at": self._selection_changed_at.get(
                    system_id, {}
                ).get(name),
                "sources": self._source_quality(
                    system_id,
                    name,
                    current,
                ),
            }
            for name, selected in sorted(self._selection.get(system_id, {}).items())
        }

    def _record_retained(
        self,
        transport: ZendureTransport,
        message: CloudMqttMessage,
    ) -> None:
        system_id = message.device_candidate_id
        payload = message.parsed_payload
        if system_id is None or not isinstance(payload, dict):
            return
        properties = payload.get("properties")
        if isinstance(properties, dict):
            destination = self._retained_main.setdefault(
                (transport, system_id), {}
            )
            for raw_name in properties:
                mapping = MAIN_PROPERTY_MAPPINGS.get(str(raw_name))
                if mapping is not None:
                    destination[mapping.target] = message.retained
            if "faultLevel" in properties or "is_error" in properties:
                destination["protection_active"] = any(
                    destination.get(key, False) for key in ("fault_code", "is_error")
                )
        packs = payload.get("packData")
        if not isinstance(packs, list):
            return
        for pack in packs:
            if not isinstance(pack, dict):
                continue
            pack_id = _pack_id(pack)
            if pack_id is None:
                continue
            destination = self._retained_packs.setdefault(
                (transport, system_id, pack_id), {}
            )
            for raw_name in pack:
                mapping = PACK_PROPERTY_MAPPINGS.get(str(raw_name))
                if mapping is not None:
                    destination[mapping.target] = message.retained
            if "power" in pack:
                destination["charge_power_w"] = message.retained
                destination["discharge_power_w"] = message.retained
            if "faultLevel" in pack:
                destination["protection_active"] = message.retained

    def _source_quality(
        self,
        system_id: str,
        property_name: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        values = []
        for source, normalizer in self._normalizers.items():
            state = normalizer.snapshot(system_id, now=now).state
            measurement = _measurement(state, property_name)
            if measurement is None:
                continue
            observed = measurement.observed_at
            values.append({
                "transport": source.value,
                "validity": measurement.validity.value,
                "observed_at": observed,
                "age_seconds": (
                    max(0.0, (now - observed).total_seconds())
                    if observed is not None
                    else None
                ),
                "retained": self._property_retained(
                    source, system_id, property_name
                ),
            })
        return values

    def _property_retained(
        self,
        source: ZendureTransport,
        system_id: str,
        name: str,
    ) -> bool:
        if name.startswith("packs."):
            _, pack_id, target = name.split(".", 2)
            return self._retained_packs.get(
                (source, system_id, pack_id), {}
            ).get(target, False)
        target = name.split(".", 1)[-1]
        return self._retained_main.get((source, system_id), {}).get(
            target, False
        )


def _transport(value: object) -> ZendureTransport | None:
    try:
        return ZendureTransport(str(value))
    except ValueError:
        return None


def _pack_id(pack: dict[str, Any]) -> str | None:
    for key in ("sn", "packId", "packKey"):
        value = pack.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            text = str(value).strip()
            if text:
                return text
    return None


def _measurement(
    state: NeutralDeviceState,
    property_name: str,
) -> MeasuredValue[Any] | None:
    if property_name.startswith("diagnostics."):
        return state.diagnostics.get(property_name.split(".", 1)[1])
    if property_name.startswith("setpoints."):
        return getattr(state.setpoints, property_name.split(".", 1)[1], None)
    if property_name.startswith("packs."):
        _, pack_id, target = property_name.split(".", 2)
        pack = next((item for item in state.packs if item.pack_id == pack_id), None)
        return getattr(pack, target, None) if pack is not None else None
    return getattr(state, property_name, None)

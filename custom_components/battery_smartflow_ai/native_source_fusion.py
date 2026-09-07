"""Fuse independently normalized Zendure telemetry with source provenance."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime
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
from .zendure_normalizer import NormalizationResult, ZendureCloudNormalizer


_TRANSPORTS = (
    ZendureTransport.ZENSDK,
    ZendureTransport.LOCAL_MQTT,
    ZendureTransport.CLOUD_MQTT,
)
_SAFETY_PROPERTIES = frozenset(
    {"hems_active", "fault_code", "protection_active"}
)


class NativeSourceFusion:
    """Keep transport histories separate and fuse only neutral snapshots."""

    def __init__(self, bootstrap: ZendureCloudBootstrap) -> None:
        self._normalizers = {
            transport: ZendureCloudNormalizer(bootstrap) for transport in _TRANSPORTS
        }
        for item in bootstrap.devices:
            system_id = item.candidate.candidate_id
            self._normalizers[ZendureTransport.ZENSDK].set_online(system_id, None)
            self._normalizers[ZendureTransport.LOCAL_MQTT].set_online(
                system_id, None
            )
        self._arbiter = NativeReadSourceArbiter()
        self._selection: dict[str, dict[str, SelectedMeasurement[Any]]] = {}

    def apply(
        self, message: CloudMqttMessage, *, now: datetime | None = None
    ) -> NormalizationResult | None:
        transport = _transport(message.transport)
        if transport is None:
            return None
        result = self._normalizers[transport].apply(message, now=now)
        if result is None or message.device_candidate_id is None:
            return None
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

        def select(name: str, values: dict[ZendureTransport, MeasuredValue[Any]]):
            selected = self._arbiter.select(
                name,
                tuple(
                    SourceMeasurement(source, value)
                    for source, value in values.items()
                ),
                safety_critical=name.rsplit(".", 1)[-1] in _SAFETY_PROPERTIES,
            )
            trace[name] = selected
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

    def source_diagnostics(self, system_id: str) -> dict[str, Any]:
        return {
            name: {
                "transport": selected.transport.value if selected.transport else None,
                "status": selected.status.value,
                "reason": selected.reason,
                "alternatives": [source.value for source in selected.alternatives],
            }
            for name, selected in sorted(self._selection.get(system_id, {}).items())
        }


def _transport(value: object) -> ZendureTransport | None:
    try:
        return ZendureTransport(str(value))
    except ValueError:
        return None

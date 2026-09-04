"""Optional read-only Zendure runtime used by the V5.0.0-dev1 field test."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import logging
from pathlib import Path
from typing import Any, Callable

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .core.models import BatteryPackIdentity, DeviceInventory, ValueValidity
from .native_device_overview import build_native_device_overview
from .zendure_cloud import ZendureCloudClient
from .zendure_cloud_mqtt import ZendureCloudMqttTransport
from .zendure_device_matrix import VerificationLevel, resolve_zendure_device
from .zendure_hems import ZendureHemsCommandGate
from .zendure_initial_sync import (
    async_capture_initial_sync,
    export_initial_sync_capture,
)
from .zendure_normalizer import ZendureCloudNormalizer
from .zendure_privacy import ZendureDiagnosticSanitizer
from .zendure_zensdk import ZenSdkReadResult, async_read_zensdk_reports


_LOGGER = logging.getLogger(__name__)

STATUS_DISABLED = "disabled"
STATUS_DISCOVERING = "discovering"
STATUS_CONNECTING = "connecting"
STATUS_CAPTURING = "capturing"
STATUS_OBSERVING = "observing"
STATUS_ERROR = "error"
ZENSDK_POLL_INTERVAL = 5.0
ZENSDK_OFFLINE_AFTER_FAILURES = 3


@dataclass(slots=True)
class _JsonPayloadResponse:
    payload: Any
    status: int = 200

    async def json(self) -> Any:
        return self.payload


class NativeZendureRuntime:
    """Run discovery, initial sync and normalization without a write surface."""

    def __init__(
        self,
        hass: Any,
        *,
        app_token: str | None,
        selected_device: str | None,
        notify: Callable[[], None],
    ) -> None:
        self._hass = hass
        self._app_token = app_token
        self._selected_device = selected_device
        self._notify = notify
        self._task: asyncio.Task[None] | None = None
        self._transport: ZendureCloudMqttTransport | None = None
        self._status = STATUS_DISABLED if not app_token else STATUS_DISCOVERING
        self._error: str | None = None
        self._capture_path: str | None = None
        self._capture_complete: bool | None = None
        self._capture_reason: str | None = None
        self._inventory = DeviceInventory()
        self._states: dict[str, Any] = {}
        self._normalizer: ZendureCloudNormalizer | None = None
        self._processed_messages = 0
        self._last_processed_message: Any | None = None
        self._last_received_at: Any | None = None
        self._bootstrap: Any | None = None
        self._zensdk_failures: dict[str, int] = {}
        self._zensdk_last_result: dict[str, str] = {}
        self._zensdk_last_success: dict[str, datetime] = {}
        self._hems_gate = ZendureHemsCommandGate()

    @property
    def configured(self) -> bool:
        return bool(self._app_token)

    @property
    def capture_path(self) -> str | None:
        return self._capture_path

    @property
    def status(self) -> str:
        return self._status

    def start(self) -> None:
        if not self.configured or self._task is not None:
            return
        self._task = asyncio.create_task(self._async_run())

    async def async_stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._transport is not None:
            await self._transport.async_stop()
            self._transport = None

    def sensor_data(self) -> dict[str, Any]:
        return {
            "native_zendure_status": self._status,
            "native_zendure_control": "disabled_zha_active",
            "native_zendure_device_count": len(self._inventory.devices),
            "native_zendure_message_count": self._processed_messages,
            "native_zendure_last_message": (
                self._last_received_at
                or (self._transport.last_message_at if self._transport else None)
            ),
            "native_zendure_last_capture": (
                Path(self._capture_path).name if self._capture_path else None
            ),
            "native_zendure_error": self._error,
        }

    def overview_attributes(self) -> dict[str, Any]:
        systems = []
        overview = build_native_device_overview(self._inventory, self._states)
        now = datetime.now(timezone.utc)
        for system_id, item in zip(sorted(self._inventory.devices), overview):
            state = self._states.get(system_id)
            last_data = item.last_message_at
            systems.append(
                {
                    "id": item.public_id,
                    "name": item.display_name,
                    "model": item.model,
                    "profile": item.profile_key,
                    "selected": system_id == self._selected_device,
                    "online": item.online,
                    "status": item.status_text,
                    "transport": item.selected_transport.value,
                    "observed_transport": (
                        state.observed_transport.value if state is not None else None
                    ),
                    "last_data_at": last_data,
                    "hems_status": item.hems_status.value,
                    "hems_last_updated": item.hems_observed_at,
                    "hems_blocks_control": item.control_block_reason is not None,
                    "control_block_reason": item.control_block_reason,
                    "data_age_seconds": (
                        max(0.0, round((now - last_data).total_seconds(), 1))
                        if last_data is not None
                        else None
                    ),
                    "packs": [
                        {
                            "id": pack.public_id,
                            "model": pack.pack_model,
                        }
                        for pack in item.packs
                    ],
                }
            )
        return {
            "read_only": True,
            "native_control": "disabled",
            "active_control_path": "Z-HA / Home Assistant entities",
            "capture_complete": self._capture_complete,
            "capture_reason": self._capture_reason,
            "systems": systems,
        }

    def diagnostic_data(self) -> dict[str, Any]:
        return ZendureDiagnosticSanitizer().sanitize(
            {
                "status": self._status,
                "read_only": True,
                "native_control": "disabled",
                "active_control_path": "Z-HA / Home Assistant entities",
                "selected_device": self._selected_device,
                "message_count": self._processed_messages,
                "capture_complete": self._capture_complete,
                "capture_reason": self._capture_reason,
                "error": self._error,
                "zensdk_poll_interval_seconds": ZENSDK_POLL_INTERVAL,
                "zensdk_devices": self._zensdk_diagnostics(),
                "hems_devices": [
                    {
                        "device_id": system_id,
                        **self._hems_gate.diagnostics(system_id),
                    }
                    for system_id in sorted(self._inventory.devices)
                ],
                "overview": self.overview_attributes(),
            }
        )

    async def _async_run(self) -> None:
        try:
            self._set_status(STATUS_DISCOVERING)
            client = ZendureCloudClient(self._post_json)
            bootstrap = await client.async_discover(self._app_token or "")
            self._bootstrap = bootstrap
            bootstrap.register_candidates(self._inventory)
            for candidate_id in tuple(self._inventory.candidates):
                self._inventory.add_observed_system(
                    candidate_id,
                    system_id=candidate_id,
                )
            self._normalizer = ZendureCloudNormalizer(bootstrap)
            zensdk = await async_read_zensdk_reports(
                bootstrap,
                self._get_json,
            )
            self._record_zensdk_cycle(zensdk)
            self._transport = ZendureCloudMqttTransport(bootstrap)
            self._set_status(STATUS_CONNECTING)
            self._set_status(STATUS_CAPTURING)
            capture = await async_capture_initial_sync(
                bootstrap,
                self._transport,
                initial_messages=zensdk.messages,
                zensdk_attempts=zensdk.attempts,
            )
            self._capture_complete = capture.complete
            self._capture_reason = capture.completion_reason
            exported = await self._hass.async_add_executor_job(
                partial(
                    export_initial_sync_capture,
                    capture,
                    config_directory=self._hass.config.config_dir,
                )
            )
            self._capture_path = str(exported.path)
            self._consume_captured_messages(capture.messages)
            if capture.completion_reason not in {
                "initial_sync_quiet",
                "hard_timeout",
            }:
                self._error = capture.completion_reason
                self._set_status(STATUS_ERROR)
                return
            self._set_status(STATUS_OBSERVING)
            next_zensdk_poll = (
                asyncio.get_running_loop().time() + ZENSDK_POLL_INTERVAL
            )
            while True:
                self._consume_messages()
                loop = asyncio.get_running_loop()
                if loop.time() >= next_zensdk_poll:
                    await self._async_poll_zensdk()
                    next_zensdk_poll = loop.time() + ZENSDK_POLL_INTERVAL
                self._refresh_snapshots()
                self._notify()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._error = _safe_reason(error)
            self._set_status(STATUS_ERROR)
            _LOGGER.warning(
                "Native Zendure read-only test stopped: %s", self._error
            )
            if self._transport is not None:
                await self._transport.async_stop()

    async def _post_json(self, url: str, **kwargs: Any) -> _JsonPayloadResponse:
        session = async_get_clientsession(self._hass)
        async with session.post(url, **kwargs) as response:
            payload = await response.json(content_type=None)
        return _JsonPayloadResponse(payload)

    async def _get_json(self, url: str, **kwargs: Any) -> _JsonPayloadResponse:
        session = async_get_clientsession(self._hass)
        async with session.get(url, **kwargs) as response:
            payload = (
                await response.json(content_type=None)
                if response.status == 200
                else None
            )
            return _JsonPayloadResponse(payload, response.status)

    def _consume_messages(self) -> None:
        if self._transport is None or self._normalizer is None:
            return
        messages = self._transport.messages
        start = 0
        if self._last_processed_message is not None:
            for index, message in enumerate(messages):
                if message is self._last_processed_message:
                    start = index + 1
                    break
        new_messages = messages[start:]
        self._apply_messages(new_messages)
        if new_messages:
            self._last_processed_message = new_messages[-1]

    def _consume_captured_messages(self, messages: tuple[Any, ...]) -> None:
        """Apply ZenSDK seed data and MQTT messages captured during startup."""

        self._apply_messages(messages)
        cloud_messages = [
            message for message in messages if message.transport == "cloud_mqtt"
        ]
        if cloud_messages:
            self._last_processed_message = cloud_messages[-1]

    async def _async_poll_zensdk(self) -> None:
        if self._bootstrap is None:
            return
        result = await async_read_zensdk_reports(
            self._bootstrap,
            self._get_json,
        )
        self._record_zensdk_cycle(result)
        self._apply_messages(result.messages)

    def _record_zensdk_cycle(self, result: ZenSdkReadResult) -> None:
        successful = {
            message.device_candidate_id
            for message in result.messages
            if message.device_candidate_id is not None
        }
        attempted = {item.device_candidate_id for item in result.attempts}
        last_results = {
            candidate_id: next(
                item.result
                for item in reversed(result.attempts)
                if item.device_candidate_id == candidate_id
            )
            for candidate_id in attempted
        }
        observed_at = datetime.now(timezone.utc)
        for candidate_id in attempted:
            self._zensdk_last_result[candidate_id] = last_results[candidate_id]
            if candidate_id in successful:
                self._zensdk_failures[candidate_id] = 0
                self._zensdk_last_success[candidate_id] = observed_at
                if self._normalizer is not None:
                    self._normalizer.set_online(candidate_id, True)
                if candidate_id in self._inventory.devices:
                    self._inventory.mark_available(candidate_id)
                continue
            failures = self._zensdk_failures.get(candidate_id, 0) + 1
            self._zensdk_failures[candidate_id] = failures
            if failures >= ZENSDK_OFFLINE_AFTER_FAILURES:
                if self._normalizer is not None:
                    self._normalizer.set_online(candidate_id, False)
                if candidate_id in self._inventory.devices:
                    self._inventory.mark_unavailable(candidate_id)

    def _refresh_snapshots(self) -> None:
        if self._normalizer is None:
            return
        for system_id in tuple(self._inventory.devices):
            result = self._normalizer.snapshot(
                system_id,
                now=datetime.now(timezone.utc),
            )
            self._apply_state(result.state)

    def _zensdk_diagnostics(self) -> list[dict[str, Any]]:
        return [
            {
                "device_id": candidate_id,
                "last_result": self._zensdk_last_result.get(candidate_id),
                "consecutive_failures": self._zensdk_failures.get(candidate_id, 0),
                "last_success": self._zensdk_last_success.get(candidate_id),
            }
            for candidate_id in sorted(self._zensdk_last_result)
        ]

    def _apply_messages(self, messages: tuple[Any, ...]) -> None:
        if self._normalizer is None:
            return
        for message in messages:
            result = self._normalizer.apply(message)
            if result is None:
                continue
            self._apply_state(result.state)
        if messages:
            self._last_received_at = max(
                message.received_at for message in messages
            )
            self._processed_messages += len(messages)

    def _apply_state(self, state: Any) -> None:
        self._states[state.system_id] = state
        device = self._inventory.devices[state.system_id]
        identity = device.native_identities[0] if device.native_identities else None
        profile = resolve_zendure_device(identity) if identity is not None else None
        capability = (
            profile.hems_status if profile is not None else VerificationLevel.UNKNOWN
        )
        decision = self._hems_gate.update(
            state.system_id,
            state.hems_active,
            capability=capability,
        )
        self._inventory.set_hems_status(
            state.system_id,
            decision.status,
            observed_at=decision.observed_at,
        )
        packs = tuple(
            BatteryPackIdentity(
                pack_id=pack.pack_id,
                parent_system_id=state.system_id,
                pack_type=_value(pack.pack_type),
                firmware=_value(pack.firmware),
            )
            for pack in state.packs
        )
        self._inventory.reconcile_packs(state.system_id, packs)

    def _set_status(self, value: str) -> None:
        self._status = value
        self._notify()

def _safe_reason(error: Exception) -> str:
    reason = getattr(error, "reason", None)
    allowed = {
        "invalid_token", "invalid_or_expired_token", "cannot_connect", "timeout",
        "invalid_response", "no_devices", "no_mqtt_credentials",
        "connection_timeout", "invalid_broker_url", "mqtt_dependency_missing",
        "no_routable_devices", "subscribe_failed", "capture_write_failed",
        "state_request_failed",
    }
    return str(reason) if reason in allowed else "native_test_failed"


def _value(measured: Any) -> str | None:
    return str(measured.value) if measured.validity is ValueValidity.VALID else None

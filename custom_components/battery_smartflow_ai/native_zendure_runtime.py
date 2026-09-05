"""Native Zendure observation plus one explicit development write test."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import partial
import logging
from pathlib import Path
from typing import Any, Callable

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .core.models import (
    BatteryPackIdentity,
    CommandExecutionResult,
    CommandExecutionStatus,
    DeviceCommand,
    DeviceControlState,
    DeviceInventory,
    MainDevice,
    NativeDeviceIdentity,
    ValueValidity,
    ZendureTransport,
)
from .native_device_command_gate import (
    NativeCommandContext,
    NativeCommandRequest,
    NativeDeviceCommandGate,
)
from .native_command_verification import NativeCommandVerificationManager
from .native_device_overview import build_native_device_overview
from .zendure_cloud import ZendureCloudClient
from .zendure_cloud_mqtt import ConnectionState, ZendureCloudMqttTransport
from .zendure_device_matrix import (
    VerificationLevel,
    preferred_local_transport,
    resolve_zendure_device,
)
from .zendure_hems import ZendureHemsCommandGate
from .zendure_initial_sync import (
    async_capture_initial_sync,
    export_initial_sync_capture,
)
from .zendure_first_write import (
    NativeWriteVerification,
    PropertyReadback,
    TransportWriteResult,
    async_verify_reversible_write,
)
from .zendure_normalizer import ZendureCloudNormalizer
from .zendure_privacy import ZendureDiagnosticSanitizer
from .zendure_zensdk import (
    ZenSdkReadResult,
    async_read_zensdk_reports,
    async_write_zensdk_property,
)
from .zendure_zensdk_commands import (
    ZenSdkCommandStatus,
    ZendureZenSdkCommandAdapter,
)


_LOGGER = logging.getLogger(__name__)

STATUS_DISABLED = "disabled"
STATUS_DISCOVERING = "discovering"
STATUS_CONNECTING = "connecting"
STATUS_CAPTURING = "capturing"
STATUS_OBSERVING = "observing"
STATUS_ERROR = "error"
ZENSDK_POLL_INTERVAL = 5.0
ZENSDK_OFFLINE_AFTER_FAILURES = 3
ZENSDK_MAX_DATA_AGE = 30.0
ZENSDK_MAX_RETRY_INTERVAL = 60.0


@dataclass(slots=True)
class _JsonPayloadResponse:
    payload: Any
    status: int = 200

    async def json(self) -> Any:
        return self.payload


class NativeZendureRuntime:
    """Observe devices; normal automation retains the Home Assistant backend."""

    def __init__(
        self,
        hass: Any,
        *,
        app_token: str | None,
        selected_device: str | None,
        notify: Callable[[], None],
        control_enabled: bool = False,
    ) -> None:
        self._hass = hass
        self._app_token = app_token
        self._selected_device = selected_device
        self._control_enabled = bool(control_enabled)
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
        self._zensdk_next_poll: dict[str, float] = {}
        self._zensdk_poll_delay: dict[str, float] = {}
        self._hems_gate = ZendureHemsCommandGate()
        self._first_write_result: NativeWriteVerification | None = None
        self._write_lock = asyncio.Lock()
        self._write_sequence = 0
        self._command_verification = NativeCommandVerificationManager()
        self._zensdk_command_adapter: ZendureZenSdkCommandAdapter | None = None
        self._last_command_result: dict[str, Any] | None = None

    @property
    def configured(self) -> bool:
        return bool(self._app_token)

    @property
    def control_enabled(self) -> bool:
        """Native ownership is explicit and never inferred from setup."""

        return self._control_enabled

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
            "native_zendure_control": (
                self._control_sensor_state()
                if self._control_enabled
                else "disabled_zha_active"
            ),
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
            "native_zendure_first_write": (
                self._first_write_result.status.value
                if self._first_write_result is not None else "not_run"
            ),
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
                    "transport": (
                        self._selected_local_transport().value
                        if self._control_enabled
                        and system_id == self._selected_device
                        and self._selected_local_transport() is not None
                        else item.selected_transport.value
                    ),
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
            "read_only": False,
            "native_control": "enabled" if self._control_enabled else "disabled",
            "active_control_path": (
                _control_path_name(self._selected_local_transport())
                if self._control_enabled
                else "Z-HA / Home Assistant entities"
            ),
            "capture_complete": self._capture_complete,
            "capture_reason": self._capture_reason,
            "systems": systems,
            "first_write_test": (
                self._first_write_result.diagnostics()
                if self._first_write_result is not None else None
            ),
        }

    def diagnostic_data(self) -> dict[str, Any]:
        return ZendureDiagnosticSanitizer().sanitize(
            {
                "status": self._status,
                "read_only": False,
                "native_control": "enabled" if self._control_enabled else "disabled",
                "active_control_path": (
                    _control_path_name(self._selected_local_transport())
                    if self._control_enabled
                    else "Z-HA / Home Assistant entities"
                ),
                "selected_control_transport": (
                    self._selected_local_transport().value
                    if self._selected_local_transport() is not None
                    else None
                ),
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
                        **self._hems_activity_diagnostics(system_id),
                    }
                    for system_id in sorted(self._inventory.devices)
                ],
                "first_write_test": (
                    self._first_write_result.diagnostics()
                    if self._first_write_result is not None else None
                ),
                "command_verification": self._command_verification.diagnostics(),
                "cloud_command_verification": (
                    self._transport.command_diagnostics
                    if self._transport is not None else {"commands": []}
                ),
                "last_command_result": self._last_command_result,
                "overview": self.overview_attributes(),
            }
        )

    async def async_run_first_write_test(self) -> NativeWriteVerification:
        """Run the explicit SF2400AC ZenSDK +1 W write and restore test."""

        async with self._write_lock:
            if self._bootstrap is None or self._selected_device is None:
                raise ValueError("native_device_not_ready")
            state = self._states.get(self._selected_device)
            source_device = self._inventory.devices.get(self._selected_device)
            if state is None or source_device is None:
                raise ValueError("native_device_not_ready")
            current = state.setpoints.output_limit_w
            now = datetime.now(timezone.utc)
            if (
                not current.valid or current.observed_at is None
                or (now - current.observed_at).total_seconds() > 15
            ):
                raise ValueError("output_limit_not_fresh")
            source_identity = source_device.native_identities[0]
            local_identity = NativeDeviceIdentity(
                transport=ZendureTransport.ZENSDK,
                device_id=source_identity.device_id,
                serial_number=source_identity.serial_number,
                product_id=source_identity.product_id,
                product_model=source_identity.product_model,
            )
            test_device = MainDevice(
                system_id=self._selected_device,
                display_name=source_device.display_name,
                model=source_device.model,
                profile_key=source_device.profile_key,
                control_state=DeviceControlState.ACTIVE,
                selected_transport=ZendureTransport.ZENSDK,
                available_transports=frozenset({ZendureTransport.ZENSDK}),
                native_identities=(local_identity,),
                online=True,
                hems_status=source_device.hems_status,
                hems_active=source_device.hems_active,
            )
            inventory = DeviceInventory(devices=(test_device,))
            original = float(current.value)
            profile = resolve_zendure_device(local_identity)
            maximum = profile.profile.capabilities.max_output_w if profile else original
            target = original + 1.0 if original < maximum else original - 1.0
            command = DeviceCommand(
                "output", output_limit_w=target, reason="native_first_write_test",
                should_write_mode=False, should_write_input=False,
                should_write_output=True,
            )
            request = NativeCommandRequest(
                self._selected_device, ZendureTransport.ZENSDK, command
            )
            context = NativeCommandContext(
                inventory=inventory, states={self._selected_device: state},
                selected_device_id=self._selected_device,
                native_control_enabled=True,
                available_transports=frozenset({ZendureTransport.ZENSDK}),
            )

            async def send(prop: str, value: float, _correlation: str):
                self._write_sequence += 1
                outcome = await async_write_zensdk_property(
                    self._bootstrap, self._selected_device, prop, int(value),
                    self._write_sequence, self._post_json,
                )
                return TransportWriteResult(outcome.accepted, outcome.http_status)

            async def read():
                result = await async_read_zensdk_reports(
                    self._bootstrap, self._get_json
                )
                self._record_zensdk_cycle(result)
                self._apply_messages(result.messages)
                for message in result.messages:
                    if message.device_candidate_id != self._selected_device:
                        continue
                    payload = message.parsed_payload or {}
                    properties = payload.get("properties", payload)
                    value = properties.get("outputLimit")
                    if isinstance(value, (int, float)):
                        return PropertyReadback(float(value), message.received_at)
                return None

            self._first_write_result = await async_verify_reversible_write(
                gate=NativeDeviceCommandGate(self._hems_gate), request=request,
                context=context, property_name="outputLimit",
                original_value=original, requested_value=target,
                send_property=send, read_property=read,
                verification_manager=self._command_verification,
            )
            self._notify()
            return self._first_write_result

    async def async_execute_device_command(
        self, command: DeviceCommand
    ) -> CommandExecutionResult:
        """Route one neutral PowerController command through the native stack."""

        if not self._control_enabled:
            return self._remember_command_result(_command_result(
                CommandExecutionStatus.SKIPPED, "native_control_disabled"
            ))
        async with self._write_lock:
            if (
                self._status != STATUS_OBSERVING
                or self._selected_device is None
            ):
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED, "native_transport_not_ready"
                ))
            state = self._states.get(self._selected_device)
            source_device = self._inventory.devices.get(self._selected_device)
            if state is None or source_device is None or not _fresh_native_state(state):
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED, "native_state_not_fresh"
                ))
            control_transport = preferred_local_transport(
                source_device.native_identities[0]
            ) if source_device.native_identities else None
            if control_transport is None:
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED,
                    "native_local_transport_unsupported",
                ))
            if not self._control_transport_ready(control_transport):
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED,
                    f"native_{control_transport.value}_not_ready",
                ))
            source_identities = tuple(
                identity for identity in source_device.native_identities
                if identity.transport is ZendureTransport.CLOUD_MQTT
            )
            if len(source_identities) != 1:
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED, "native_identity_not_unique"
                ))
            source_identity = source_identities[0]
            control_identity = NativeDeviceIdentity(
                transport=control_transport,
                device_id=source_identity.device_id,
                serial_number=source_identity.serial_number,
                product_id=source_identity.product_id,
                product_model=source_identity.product_model,
            )
            active_device = replace(
                source_device,
                control_state=DeviceControlState.ACTIVE,
                selected_transport=control_transport,
                available_transports=frozenset({control_transport}),
                native_identities=(control_identity,),
            )
            final_command = _skip_matching_writes(command, state)
            offgrid_power = getattr(state, "offgrid_power_w", None)
            final_command = replace(
                final_command,
                metadata={
                    **final_command.metadata,
                    "native_offgrid_power_w": (
                        float(offgrid_power.value)
                        if offgrid_power is not None and offgrid_power.valid
                        else None
                    ),
                },
            )
            if not _has_writes(final_command):
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED, "native_setpoints_unchanged"
                ))
            request = NativeCommandRequest(
                self._selected_device, control_transport, final_command
            )
            context = NativeCommandContext(
                inventory=DeviceInventory(devices=(active_device,)),
                states={self._selected_device: state},
                selected_device_id=self._selected_device,
                native_control_enabled=True,
                available_transports=frozenset({control_transport}),
            )
            if (
                control_transport is not ZendureTransport.ZENSDK
                or self._zensdk_command_adapter is None
            ):
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED,
                    "native_local_transport_not_implemented",
                ))
            gate, transport = await NativeDeviceCommandGate(self._hems_gate).execute(
                request, context, self._zensdk_command_adapter.execute
            )
            if not gate.accepted or transport is None:
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.SKIPPED,
                    ",".join(gate.reasons) or "native_gate_blocked",
                ))
            if transport.status is not ZenSdkCommandStatus.SENT:
                return self._remember_command_result(_command_result(
                    CommandExecutionStatus.FAILED, transport.reason
                ))
            return self._remember_command_result(CommandExecutionResult(
                status=CommandExecutionStatus.APPLIED,
                reason=transport.reason,
                mode_written=final_command.should_write_mode,
                input_written=final_command.should_write_input,
                output_written=final_command.should_write_output,
            ))

    def _remember_command_result(
        self, result: CommandExecutionResult
    ) -> CommandExecutionResult:
        """Keep one privacy-safe dispatch outcome for field diagnostics."""

        self._last_command_result = {
            "status": str(result.status),
            "reason": str(result.reason),
            "mode_written": bool(result.mode_written),
            "input_written": bool(result.input_written),
            "output_written": bool(result.output_written),
            "recorded_at": datetime.now(timezone.utc),
        }
        return result

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
            self._zensdk_command_adapter = ZendureZenSdkCommandAdapter(
                bootstrap,
                self._post_json,
                self._command_verification,
            )
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
            self._initialize_zensdk_schedule(asyncio.get_running_loop().time())
            while True:
                self._consume_messages()
                loop = asyncio.get_running_loop()
                await self._async_poll_zensdk(now_monotonic=loop.time())
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
        return _JsonPayloadResponse(payload, response.status)

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

    async def _async_poll_zensdk(self, *, now_monotonic: float | None = None) -> None:
        if self._bootstrap is None:
            return
        current = (
            asyncio.get_running_loop().time()
            if now_monotonic is None else now_monotonic
        )
        due = self._due_zensdk_devices(current)
        if not due:
            return
        result = await async_read_zensdk_reports(
            self._bootstrap,
            self._get_json,
            candidate_ids=frozenset(due),
        )
        self._record_zensdk_cycle(result)
        self._apply_messages(result.messages)
        for candidate_id in due:
            self._schedule_zensdk_poll(candidate_id, current)

    def _initialize_zensdk_schedule(self, now_monotonic: float) -> None:
        """Schedule every supported local device independently."""

        for candidate_id in self._zensdk_last_result:
            self._schedule_zensdk_poll(candidate_id, now_monotonic)

    def _schedule_zensdk_poll(
        self, candidate_id: str, now_monotonic: float
    ) -> None:
        failures = self._zensdk_failures.get(candidate_id, 0)
        delay = (
            ZENSDK_POLL_INTERVAL
            if failures == 0
            else min(
                ZENSDK_MAX_RETRY_INTERVAL,
                ZENSDK_POLL_INTERVAL * (2 ** min(failures, 4)),
            )
        )
        self._zensdk_poll_delay[candidate_id] = delay
        self._zensdk_next_poll[candidate_id] = now_monotonic + delay

    def _due_zensdk_devices(self, now_monotonic: float) -> tuple[str, ...]:
        return tuple(
            candidate_id
            for candidate_id, due_at in sorted(self._zensdk_next_poll.items())
            if now_monotonic >= due_at
        )

    def _record_zensdk_cycle(self, result: ZenSdkReadResult) -> None:
        successful: dict[str, datetime] = {}
        for message in result.messages:
            device_id = message.device_candidate_id
            if device_id is not None and message.transport == "zensdk":
                successful[device_id] = max(
                    successful.get(device_id, message.received_at), message.received_at
                )
        attempted = {item.device_candidate_id for item in result.attempts}
        last_results = {
            candidate_id: next(
                item.result
                for item in reversed(result.attempts)
                if item.device_candidate_id == candidate_id
            )
            for candidate_id in attempted
        }
        for candidate_id in attempted:
            self._zensdk_last_result[candidate_id] = last_results[candidate_id]
            if candidate_id in successful:
                self._zensdk_failures[candidate_id] = 0
                self._zensdk_last_success[candidate_id] = successful[candidate_id]
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
        now = datetime.now(timezone.utc)
        for system_id in tuple(self._inventory.devices):
            self._normalizer.set_hems_monitoring(
                system_id,
                self._transport is not None
                and self._transport.state is ConnectionState.CONNECTED,
                observed_at=now,
            )
            result = self._normalizer.snapshot(
                system_id,
                now=now,
            )
            self._apply_state(result.state)

    def _hems_activity_diagnostics(self, system_id: str) -> dict[str, Any]:
        if self._normalizer is None:
            return {}
        value = self._normalizer.hems_diagnostics(
            system_id,
            now=datetime.now(timezone.utc),
        )
        return {
            "activity_source": value.source,
            "activity_monitoring": value.monitoring,
            "activity_monitoring_started": value.monitoring_started_at,
            "last_activity": value.last_activity_at,
            "activity_quiet_seconds": value.quiet_seconds,
            "activity_confirmation_window_seconds": (
                value.confirmation_window_seconds
            ),
        }

    def _zensdk_diagnostics(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """Report local transport health independently of merged device state."""
        current = now or datetime.now(timezone.utc)
        return [
            {
                "device_id": candidate_id,
                "last_result": self._zensdk_last_result.get(candidate_id),
                "consecutive_failures": self._zensdk_failures.get(candidate_id, 0),
                "last_success": self._zensdk_last_success.get(candidate_id),
                "poll_delay_seconds": self._zensdk_poll_delay.get(candidate_id),
                "retry_interval_cap_seconds": ZENSDK_MAX_RETRY_INTERVAL,
                **self._zensdk_health(candidate_id, current),
            }
            for candidate_id in sorted(self._zensdk_last_result)
        ]

    def _zensdk_health(self, candidate_id: str, now: datetime) -> dict[str, Any]:
        last = self._zensdk_last_success.get(candidate_id)
        age = (now - last).total_seconds() if last is not None else None
        failures = self._zensdk_failures.get(candidate_id, 0)
        if failures >= ZENSDK_OFFLINE_AFTER_FAILURES:
            status = "offline"
        elif age is None:
            status = "unknown"
        elif age < 0 or age > ZENSDK_MAX_DATA_AGE:
            status = "stale"
        elif failures:
            status = "degraded"
        else:
            status = "available"
        return {
            "transport": "zensdk",
            "availability": status,
            "available": status == "available",
            "data_age_seconds": round(age, 3) if age is not None else None,
            "maximum_data_age_seconds": ZENSDK_MAX_DATA_AGE,
        }

    def _apply_messages(self, messages: tuple[Any, ...]) -> None:
        if self._normalizer is None:
            return
        for message in messages:
            if (
                message.transport == "zensdk"
                and self._zensdk_command_adapter is not None
                and message.device_candidate_id is not None
                and isinstance(message.parsed_payload, dict)
            ):
                properties = message.parsed_payload.get("properties")
                if isinstance(properties, dict):
                    self._zensdk_command_adapter.observe_properties(
                        device_id=message.device_candidate_id,
                        properties=properties,
                        observed_at=message.received_at,
                    )
            result = self._normalizer.apply(message)
            if result is None:
                continue
            self._apply_state(result.state)
        if messages:
            self._last_received_at = max(
                message.received_at for message in messages
            )
            self._processed_messages += len(messages)

    def _control_transport_ready(self, transport: ZendureTransport) -> bool:
        if transport is ZendureTransport.ZENSDK:
            return bool(
                self._bootstrap is not None
                and self._zensdk_command_adapter is not None
                and self._selected_device is not None
                and self._zensdk_health(
                    self._selected_device, datetime.now(timezone.utc)
                )["available"]
            )
        return False

    def _selected_local_transport(self) -> ZendureTransport | None:
        if self._selected_device is None:
            return None
        device = self._inventory.devices.get(self._selected_device)
        if device is None or not device.native_identities:
            return None
        return preferred_local_transport(device.native_identities[0])

    def _control_sensor_state(self) -> str:
        transport = self._selected_local_transport()
        if transport is ZendureTransport.ZENSDK:
            return "native_zensdk_active"
        if transport is ZendureTransport.LOCAL_MQTT:
            return "native_local_mqtt_active"
        return "native_local_unsupported"

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


def _control_path_name(transport: ZendureTransport | None) -> str:
    if transport is ZendureTransport.ZENSDK:
        return "Native Zendure ZenSDK"
    if transport is ZendureTransport.LOCAL_MQTT:
        return "Native Zendure Local MQTT"
    return "Native Zendure local transport unavailable"


def _value(measured: Any) -> str | None:
    return str(measured.value) if measured.validity is ValueValidity.VALID else None


def _fresh_native_state(state: Any, *, maximum_age_seconds: float = 30.0) -> bool:
    """Require fresh device safety data; HEMS freshness has its own gate.

    The HEMS activity fallback deliberately keeps the timestamp of the last
    observed activity.  Once its quiet confirmation window has elapsed that
    timestamp may therefore be older than this generic state window while the
    dedicated HEMS command gate still has an explicit, safe decision.  Requiring
    it here as well would permanently suppress otherwise safe commands.
    """

    now = datetime.now(timezone.utc)
    required = (state.online, state.protection_active)
    return all(
        item.valid
        and item.observed_at is not None
        and 0 <= (now - item.observed_at).total_seconds() <= maximum_age_seconds
        for item in required
    )


def _skip_matching_writes(command: DeviceCommand, state: Any) -> DeviceCommand:
    mode = state.mode
    mode_matches = mode.valid and (
        (command.ac_mode == "input" and str(mode.value) in {"charge", "input"})
        or (command.ac_mode == "output" and str(mode.value) in {"discharge", "output"})
    )
    input_value = state.setpoints.input_limit_w
    output_value = state.setpoints.output_limit_w
    charge_power = state.charge_power_w
    discharge_power = state.discharge_power_w
    input_is_inactive = bool(
        float(command.input_limit_w) > 0
        and charge_power.valid
        and float(charge_power.value) <= 0
    )
    output_is_inactive = bool(
        float(command.output_limit_w) > 0
        and discharge_power.valid
        and float(discharge_power.value) <= 0
    )
    force_input_write = bool(
        command.ac_mode == "input"
        and float(command.input_limit_w) > 0
        and input_is_inactive
    )
    force_output_write = bool(
        command.ac_mode == "output"
        and float(command.output_limit_w) > 0
        and output_is_inactive
    )
    should_write_input = force_input_write or (
        command.should_write_input and not (
            not input_is_inactive
            and input_value.valid
            and float(input_value.value) == float(command.input_limit_w)
        )
    )
    should_write_output = force_output_write or (
        command.should_write_output and not (
            not output_is_inactive
            and output_value.valid
            and float(output_value.value) == float(command.output_limit_w)
        )
    )
    should_write_mode = command.should_write_mode and not mode_matches
    return replace(
        command,
        metadata=dict(command.metadata),
        should_write_mode=should_write_mode,
        should_write_input=should_write_input,
        should_write_output=should_write_output,
        skipped=not any((
            should_write_mode,
            should_write_input,
            should_write_output,
            command.should_write_min_soc,
            command.should_write_max_soc,
        )),
        skip_reason=(
            "none"
            if any((should_write_mode, should_write_input, should_write_output))
            else command.skip_reason
        ),
    )


def _has_writes(command: DeviceCommand) -> bool:
    return any((
        command.should_write_mode, command.should_write_input,
        command.should_write_output, command.should_write_min_soc,
        command.should_write_max_soc,
    ))


def _command_result(
    status: CommandExecutionStatus, reason: str
) -> CommandExecutionResult:
    return CommandExecutionResult(status=status, reason=reason)

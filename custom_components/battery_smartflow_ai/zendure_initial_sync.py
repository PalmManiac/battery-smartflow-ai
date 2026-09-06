"""Event-driven, privacy-safe Zendure initial-sync capture for V5."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .zendure_cloud import ZendureCloudBootstrap
from .zendure_cloud_mqtt import (
    CloudMqttMessage,
    ConnectionState,
    ZendureCloudMqttTransport,
)
from .zendure_privacy import ZendureDiagnosticSanitizer
from .zendure_zensdk import ZenSdkReadAttempt

SCHEMA = "battery_smartflow_ai.zendure_initial_sync"
SCHEMA_VERSION = 1
INITIAL_SYNC_DIRECTORY = Path("bsfai") / "debug"
DEFAULT_QUIET_PERIOD = 3.0
DEFAULT_HARD_TIMEOUT = 30.0
DEFAULT_MAX_EXPORT_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_RETAINED_CAPTURES = 3
_INITIAL_SYNC_FILE_GLOB = "zendure_initial_sync_*.json"


class InitialSyncExportError(RuntimeError):
    """Raised when a sanitized capture cannot be exported safely."""


@dataclass(frozen=True, slots=True)
class InitialSyncCaptureResult:
    """Completed or diagnostically useful partial initial-sync capture."""

    started_at: datetime
    finished_at: datetime
    complete: bool
    completion_reason: str
    discovery: tuple[Mapping[str, Any], ...]
    connection_events: tuple[Mapping[str, Any], ...]
    messages: tuple[CloudMqttMessage, ...]
    expected_devices: tuple[str, ...]
    zensdk_attempts: tuple[ZenSdkReadAttempt, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Build one detached package and sanitize it with one alias namespace."""

        mqtt_messages = [
            _raw_message(item)
            for item in self.messages
            if item.transport == "cloud_mqtt"
        ]
        zensdk_responses = [
            _raw_message(item)
            for item in self.messages
            if item.transport == "zensdk"
        ]
        package = {
            "meta": {
                "schema": SCHEMA,
                "schema_version": SCHEMA_VERSION,
                "started_at": _iso(self.started_at),
                "finished_at": _iso(self.finished_at),
                "complete": self.complete,
                "completion_reason": self.completion_reason,
                "read_only": True,
            },
            "raw_communication": {
                "device_list": [dict(item) for item in self.discovery],
                "connection_events": [dict(item) for item in self.connection_events],
                "mqtt_messages": mqtt_messages,
                "zensdk_requests": [
                    {
                        "device_id": _diagnostic_device_id(
                            item.device_candidate_id
                        ),
                        "path": "/properties/report",
                        "address_source": item.address_source,
                        "result": item.result,
                        "http_status": item.http_status,
                    }
                    for item in self.zensdk_attempts
                ],
                "zensdk_responses": zensdk_responses,
            },
            "bsfai_interpretation": _build_summary(
                self.discovery,
                self.messages,
                self.expected_devices,
            ),
        }
        return ZendureDiagnosticSanitizer().sanitize(package)


@dataclass(frozen=True, slots=True)
class InitialSyncExportResult:
    path: Path
    size_bytes: int
    removed_old_captures: int = 0


class ZendureInitialSyncRecorder:
    """Track novelty and completion without becoming a long-term logger."""

    def __init__(
        self,
        bootstrap: ZendureCloudBootstrap,
        *,
        quiet_period: float = DEFAULT_QUIET_PERIOD,
        hard_timeout: float = DEFAULT_HARD_TIMEOUT,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        initial_messages: tuple[CloudMqttMessage, ...] = (),
        zensdk_attempts: tuple[ZenSdkReadAttempt, ...] = (),
    ) -> None:
        if quiet_period <= 0 or hard_timeout <= quiet_period:
            raise ValueError("hard_timeout must be greater than quiet_period")
        self._bootstrap = bootstrap
        self._quiet_period = quiet_period
        self._hard_timeout = hard_timeout
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._started_at = self._clock()
        self._started_monotonic = monotonic()
        self._last_novel = self._started_monotonic
        self._seen_topics: set[str] = set()
        self._seen_properties: set[str] = set()
        self._seen_devices: set[str] = set()
        self._messages: list[CloudMqttMessage] = []
        self._zensdk_attempts = zensdk_attempts
        self._connection_events: list[dict[str, Any]] = []
        self._last_connection_signature: tuple[Any, ...] | None = None
        self._expected_devices = tuple(
            sorted(
                item.candidate.candidate_id
                for item in bootstrap.devices
                if item.candidate.identity.device_id is not None
            )
        )
        for message in initial_messages:
            self.observe_message(message)

    def observe_connection(
        self,
        state: ConnectionState,
        *,
        variant: str = "unknown",
        phase: str = "unknown",
        diagnostics: Mapping[str, str | bool] | None = None,
    ) -> None:
        safe_diagnostics = dict(diagnostics or {})
        signature = (state, variant, phase, tuple(sorted(safe_diagnostics.items())))
        if signature == self._last_connection_signature:
            return
        self._last_connection_signature = signature
        self._connection_events.append({
            "timestamp": _iso(self._clock()),
            "state": state.value,
            "variant": variant,
            "phase": phase,
            **safe_diagnostics,
        })

    def observe_message(self, message: CloudMqttMessage) -> None:
        """Record every message; only novel structure extends the quiet phase."""

        self._messages.append(message)
        novel = message.topic not in self._seen_topics
        self._seen_topics.add(message.topic)
        properties = _property_paths(message.parsed_payload)
        if properties - self._seen_properties:
            novel = True
        self._seen_properties.update(properties)
        if message.device_candidate_id is not None:
            self._seen_devices.add(message.device_candidate_id)
        if novel:
            self._last_novel = self._monotonic()

    def completion(self) -> tuple[bool, str] | None:
        now = self._monotonic()
        if now - self._started_monotonic >= self._hard_timeout:
            return False, "hard_timeout"
        all_devices_seen = bool(self._expected_devices) and set(
            self._expected_devices
        ).issubset(self._seen_devices)
        if all_devices_seen and now - self._last_novel >= self._quiet_period:
            return True, "initial_sync_quiet"
        return None

    def finish(
        self,
        *,
        complete: bool,
        reason: str,
    ) -> InitialSyncCaptureResult:
        return InitialSyncCaptureResult(
            started_at=self._started_at,
            finished_at=self._clock(),
            complete=complete,
            completion_reason=reason,
            discovery=self._bootstrap.raw_device_list,
            connection_events=tuple(self._connection_events),
            messages=tuple(self._messages),
            expected_devices=self._expected_devices,
            zensdk_attempts=self._zensdk_attempts,
        )


async def async_capture_initial_sync(
    bootstrap: ZendureCloudBootstrap,
    transport: ZendureCloudMqttTransport,
    *,
    quiet_period: float = DEFAULT_QUIET_PERIOD,
    hard_timeout: float = DEFAULT_HARD_TIMEOUT,
    poll_interval: float = 0.1,
    clock: Callable[[], datetime] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    initial_messages: tuple[CloudMqttMessage, ...] = (),
    zensdk_attempts: tuple[ZenSdkReadAttempt, ...] = (),
) -> InitialSyncCaptureResult:
    """Capture discovery and MQTT startup until structural traffic is quiet."""

    recorder = ZendureInitialSyncRecorder(
        bootstrap,
        quiet_period=quiet_period,
        hard_timeout=hard_timeout,
        clock=clock,
        monotonic=monotonic,
        initial_messages=initial_messages,
        zensdk_attempts=zensdk_attempts,
    )
    cursor = 0
    def observe_transport() -> None:
        recorder.observe_connection(
            transport.state,
            variant=str(getattr(transport, "connection_variant", "unknown")),
            phase=str(getattr(transport, "connection_phase", "unknown")),
            diagnostics=getattr(transport, "connection_diagnostics", None),
        )

    observe_transport()
    try:
        await transport.async_start(timeout=min(15.0, hard_timeout))
    except Exception as error:
        observe_transport()
        return recorder.finish(
            complete=False,
            reason=_safe_failure_reason(error),
        )

    while True:
        observe_transport()
        messages = transport.messages
        for message in messages[cursor:]:
            recorder.observe_message(message)
        cursor = len(messages)
        completed = recorder.completion()
        if completed is not None:
            complete, reason = completed
            return recorder.finish(complete=complete, reason=reason)
        await asyncio.sleep(poll_interval)


def export_initial_sync_capture(
    capture: InitialSyncCaptureResult,
    *,
    config_directory: str | Path,
    max_export_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
    max_retained_captures: int = DEFAULT_MAX_RETAINED_CAPTURES,
) -> InitialSyncExportResult:
    """Atomically export only the already sanitized JSON representation."""

    if max_retained_captures < 1:
        raise ValueError("max_retained_captures must be at least 1")

    try:
        payload = (
            json.dumps(
                capture.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise InitialSyncExportError("capture_serialization_failed") from error
    if not 0 < len(payload) <= max_export_bytes:
        raise InitialSyncExportError("capture_size_limit_exceeded")

    directory = Path(config_directory).resolve() / INITIAL_SYNC_DIRECTORY
    temporary: Path | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        destination = _available_destination(directory, capture.finished_at)
        descriptor, name = tempfile.mkstemp(
            prefix=".zendure_initial_sync_", suffix=".tmp", dir=directory
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        temporary = None
    except OSError as error:
        raise InitialSyncExportError("capture_write_failed") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    removed = _prune_initial_sync_captures(
        directory,
        retain=max_retained_captures,
    )
    return InitialSyncExportResult(destination, len(payload), removed)


def _prune_initial_sync_captures(directory: Path, *, retain: int) -> int:
    """Keep only recent owned captures; never touch other debug artifacts."""

    captures: list[tuple[int, str, Path]] = []
    for path in directory.glob(_INITIAL_SYNC_FILE_GLOB):
        try:
            if path.is_file() and not path.is_symlink():
                captures.append((path.stat().st_mtime_ns, path.name, path))
        except OSError:
            continue
    captures.sort(reverse=True)
    removed = 0
    for _modified, _name, path in captures[retain:]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            # A cleanup problem must not invalidate a useful new capture.
            continue
    return removed


def _raw_message(message: CloudMqttMessage) -> dict[str, Any]:
    if message.payload_format == "binary":
        payload: Any = {"base64": b64encode(message.payload).decode("ascii")}
    else:
        payload = message.parsed_payload
    return {
        "timestamp": _iso(message.received_at),
        "transport": message.transport,
        "device_id": _diagnostic_device_id(message.device_candidate_id),
        "pack_id": message.pack_id,
        "topic": message.topic,
        "payload_format": message.payload_format,
        "payload": payload,
        "known_topic": message.known_topic,
        "session": message.session_number,
    }


def _build_summary(
    discovery: tuple[Mapping[str, Any], ...],
    messages: tuple[CloudMqttMessage, ...],
    expected_devices: tuple[str, ...],
) -> dict[str, Any]:
    topics: dict[str, dict[str, Any]] = {}
    properties: dict[str, dict[str, Any]] = {}
    seen_devices: set[str] = set()
    packs: set[str] = set()
    for message in messages:
        if message.device_candidate_id:
            seen_devices.add(message.device_candidate_id)
        if message.pack_id:
            packs.add(message.pack_id)
        packs.update(_payload_pack_ids(message.parsed_payload))
        topic = topics.setdefault(
            message.topic,
            {"updates": 0, "first_seen": _iso(message.received_at), "last_seen": None},
        )
        topic["updates"] += 1
        topic["last_seen"] = _iso(message.received_at)
        for path, value, mapping_status in _summary_property_items(
            message.parsed_payload
        ):
            entry = properties.setdefault(
                path,
                {
                    "types": [],
                    "example": value,
                    "updates": 0,
                    "first_seen": _iso(message.received_at),
                    "last_seen": None,
                    "mapping_status": mapping_status,
                },
            )
            value_type = _type_name(value)
            if value_type not in entry["types"]:
                entry["types"].append(value_type)
            entry["updates"] += 1
            entry["last_seen"] = _iso(message.received_at)
    return {
        "device_count": len(expected_devices),
        "devices_with_messages": sorted(
            _diagnostic_device_id(item) for item in seen_devices
        ),
        "devices_without_messages": sorted(
            _diagnostic_device_id(item)
            for item in set(expected_devices) - seen_devices
        ),
        "pack_ids": sorted(packs),
        "models": sorted(
            {
                str(item.get("productModel"))
                for item in discovery
                if item.get("productModel") is not None
            }
        ),
        "topics": topics,
        "properties": properties,
    }


def _payload_pack_ids(value: Any) -> set[str]:
    """Collect every stable pack identity embedded in a main-device report."""

    if not isinstance(value, Mapping):
        return set()
    raw_packs = value.get("packData")
    if not isinstance(raw_packs, list):
        return set()
    result: set[str] = set()
    for raw_pack in raw_packs:
        if not isinstance(raw_pack, Mapping):
            continue
        for key in ("sn", "packId", "packKey", "packSn", "packSN"):
            raw_id = raw_pack.get(key)
            if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool):
                pack_id = str(raw_id).strip()
                if pack_id:
                    result.add(pack_id)
                    break
    return result


def _diagnostic_device_id(value: str | None) -> str | None:
    """Use the source device ID so one device receives one export alias."""

    if value is None:
        return None
    prefix = "cloud_mqtt:"
    return value[len(prefix):] if value.startswith(prefix) else value


def _property_items(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    root = value.get("properties") if not prefix else value
    if not isinstance(root, Mapping):
        return []
    result: list[tuple[str, Any]] = []
    for key, item in root.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        result.append((path, item))
        if isinstance(item, Mapping):
            result.extend(_property_items(item, path))
    return result


def _property_paths(value: Any) -> set[str]:
    return {path for path, _value in _property_items(value)}


def _summary_property_items(value: Any) -> list[tuple[str, Any, str]]:
    """Expose mapper coverage without dropping unknown main or pack fields."""

    from .zendure_normalizer import (  # avoid coupling the raw recorder at import
        MAIN_PROPERTY_MAPPINGS,
        PACK_PROPERTY_MAPPINGS,
    )

    result = [
        (
            path,
            item,
            "mapped" if path.split(".", 1)[0] in MAIN_PROPERTY_MAPPINGS else "unmapped",
        )
        for path, item in _property_items(value)
    ]
    if not isinstance(value, Mapping):
        return result
    packs = value.get("packData")
    if not isinstance(packs, list):
        return result
    for pack in packs:
        if not isinstance(pack, Mapping):
            continue
        for raw_name, item in pack.items():
            if raw_name in {"sn", "packId", "packKey"}:
                continue
            path = f"packData[].{raw_name}"
            mapped = raw_name in PACK_PROPERTY_MAPPINGS or raw_name == "power"
            result.append((path, item, "mapped" if mapped else "unmapped"))
    return result


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, Mapping):
        return "object"
    return type(value).__name__


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("capture timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _available_destination(directory: Path, timestamp: datetime) -> Path:
    stamp = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    stem = f"zendure_initial_sync_{stamp}"
    for suffix in range(10_000):
        marker = "" if suffix == 0 else f"_{suffix}"
        candidate = directory / f"{stem}{marker}.json"
        if not candidate.exists():
            return candidate
    raise InitialSyncExportError("capture_filename_unavailable")


def _safe_failure_reason(error: Exception) -> str:
    reason = getattr(error, "reason", None)
    allowed = {
        "cannot_connect",
        "connection_timeout",
        "invalid_broker_url",
        "mqtt_dependency_missing",
        "no_routable_devices",
        "subscribe_failed",
    }
    return str(reason) if reason in allowed else "mqtt_connect_failed"

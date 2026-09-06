"""Privacy-safe, model-specific native transport measurements."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from statistics import median
from typing import Any, Iterable

from .core.models import ZendureTransport

_MAX_TELEMETRY_SAMPLES = 500
_PERCENTILE_MIN_SAMPLES = 20


@dataclass(frozen=True, slots=True)
class TransportDeviceContext:
    """Non-secret grouping fields for one physical test device."""

    model: str
    firmware: str | None = None


@dataclass(slots=True)
class _TelemetrySeries:
    timestamps: list[datetime] = field(default_factory=list)
    message_count: int = 0
    retained_messages: int = 0
    reconnects: int = 0
    disconnects: int = 0
    last_connected: bool | None = None


class NativeTransportMetrics:
    """Collect comparable command and telemetry metrics without identifiers."""

    def __init__(self) -> None:
        self._contexts: dict[str, TransportDeviceContext] = {}
        self._telemetry: dict[tuple[str, ZendureTransport], _TelemetrySeries] = {}

    def register_device(
        self,
        device_id: str,
        *,
        model: str | None,
        firmware: str | None = None,
    ) -> None:
        self._contexts[device_id] = TransportDeviceContext(
            _bounded_label(model, "unknown"),
            _bounded_label(firmware, None),
        )

    def observe_telemetry(
        self,
        *,
        device_id: str,
        transport: ZendureTransport,
        observed_at: datetime,
        retained: bool = False,
    ) -> None:
        series = self._series(device_id, transport)
        series.message_count += 1
        if not series.timestamps or observed_at > series.timestamps[-1]:
            series.timestamps.append(observed_at)
            if len(series.timestamps) > _MAX_TELEMETRY_SAMPLES:
                del series.timestamps[:-_MAX_TELEMETRY_SAMPLES]
        if retained:
            series.retained_messages += 1

    def observe_connection(
        self,
        *,
        device_id: str,
        transport: ZendureTransport,
        connected: bool,
    ) -> None:
        series = self._series(device_id, transport)
        current = bool(connected)
        if series.last_connected is False and current:
            series.reconnects += 1
        elif series.last_connected is True and not current:
            series.disconnects += 1
        series.last_connected = current

    def export(self, commands: Iterable[Any]) -> dict[str, Any]:
        """Aggregate comparable samples; omit percentiles for small samples."""

        grouped: dict[tuple[str, str, str | None, str, str], list[Any]] = defaultdict(list)
        for command in commands:
            context = self._contexts.get(
                command.device_id,
                TransportDeviceContext("unknown"),
            )
            grouped[(
                command.device_id,
                context.model,
                context.firmware,
                command.transport.value,
                command.command_type,
            )].append(command)

        command_groups = []
        for key, samples in sorted(grouped.items(), key=lambda item: item[0][1:]):
            device_id, model, firmware, transport, command_type = key
            statuses = Counter(str(item.status) for item in samples)
            effects = Counter(str(item.effect_status) for item in samples)
            timeout_count = sum(
                count for status, count in statuses.items()
                if "timeout" in status
            )
            mismatch_count = sum(
                count for status, count in statuses.items()
                if "mismatch" in status or "contradictory" in status
            )
            transport_error_count = statuses.get("transport_error", 0)
            superseded_count = statuses.get("superseded", 0)
            command_groups.append({
                "device": _public_device_id(device_id),
                "model": model,
                "firmware": firmware,
                "transport": transport,
                "command_type": command_type,
                "sample_count": len(samples),
                "status_counts": dict(sorted(statuses.items())),
                "effect_counts": dict(sorted(effects.items())),
                "timeout_count": timeout_count,
                "timeout_rate": _rate(timeout_count, len(samples)),
                "mismatch_count": mismatch_count,
                "mismatch_rate": _rate(mismatch_count, len(samples)),
                "transport_error_count": transport_error_count,
                "transport_error_rate": _rate(
                    transport_error_count,
                    len(samples),
                ),
                "superseded_count": superseded_count,
                "superseded_rate": _rate(superseded_count, len(samples)),
                "latency_seconds": {
                    "gate_to_send": _statistics(
                        _latency(item.gate_at, item.sent_at) for item in samples
                    ),
                    "send_to_transport": _statistics(
                        _latency(item.sent_at, item.transport_at) for item in samples
                    ),
                    "send_to_readback": _statistics(
                        _latency(item.sent_at, item.readback_at) for item in samples
                    ),
                    "send_to_effect": _statistics(
                        _latency(item.sent_at, item.effect_at) for item in samples
                    ),
                },
            })

        telemetry_groups = []
        for (device_id, transport), series in sorted(
            self._telemetry.items(),
            key=lambda item: (
                self._contexts.get(item[0][0], TransportDeviceContext("unknown")).model,
                item[0][1].value,
            ),
        ):
            context = self._contexts.get(device_id, TransportDeviceContext("unknown"))
            intervals = [
                (later - earlier).total_seconds()
                for earlier, later in zip(series.timestamps, series.timestamps[1:])
                if later >= earlier
            ]
            telemetry_groups.append({
                "device": _public_device_id(device_id),
                "model": context.model,
                "firmware": context.firmware,
                "transport": transport.value,
                "message_count": series.message_count,
                "interval_sample_count": max(0, len(series.timestamps) - 1),
                "update_interval_seconds": _statistics(intervals),
                "retained_message_count": series.retained_messages,
                "disconnect_count": series.disconnects,
                "reconnect_count": series.reconnects,
                "connected": series.last_connected,
            })

        return {
            "schema": "battery_smartflow_ai.native_transport_metrics",
            "schema_version": 1,
            "percentiles_minimum_samples": _PERCENTILE_MIN_SAMPLES,
            "command_groups": command_groups,
            "telemetry_groups": telemetry_groups,
        }

    def _series(
        self,
        device_id: str,
        transport: ZendureTransport,
    ) -> _TelemetrySeries:
        return self._telemetry.setdefault((device_id, transport), _TelemetrySeries())


def _statistics(values: Iterable[float | None]) -> dict[str, Any]:
    samples = sorted(float(item) for item in values if item is not None)
    if not samples:
        return {"count": 0, "median": None, "minimum": None, "maximum": None,
                "p90": None, "p95": None}
    enough = len(samples) >= _PERCENTILE_MIN_SAMPLES
    return {
        "count": len(samples),
        "median": round(median(samples), 3),
        "minimum": round(samples[0], 3),
        "maximum": round(samples[-1], 3),
        "p90": round(_percentile(samples, 0.90), 3) if enough else None,
        "p95": round(_percentile(samples, 0.95), 3) if enough else None,
    }


def _percentile(samples: list[float], fraction: float) -> float:
    index = (len(samples) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(samples) - 1)
    weight = index - lower
    return samples[lower] * (1.0 - weight) + samples[upper] * weight


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _latency(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds())


def _public_device_id(value: str) -> str:
    return f"device_{sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _bounded_label(value: Any, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    return text[:80] if text else fallback

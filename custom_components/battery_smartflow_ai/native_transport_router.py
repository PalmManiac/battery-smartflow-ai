"""Single-writer authority for native Zendure control transports."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .core.models import MainDevice, ZendureTransport
from .zendure_device_matrix import preferred_local_transport

NativeTransportSender = Callable[[Any], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class AutomaticTransportDecision:
    """Fail-closed automatic transport selection for one logical device."""

    transport: ZendureTransport | None
    reason: str

    @property
    def selected(self) -> bool:
        return self.transport is not None


def automatic_control_transport(device: MainDevice) -> AutomaticTransportDecision:
    """Resolve one local write transport from all verified device identities."""

    transports = {
        transport
        for identity in device.native_identities
        if (transport := preferred_local_transport(identity)) is not None
    }
    if not transports:
        return AutomaticTransportDecision(None, "local_transport_unsupported")
    if len(transports) != 1:
        return AutomaticTransportDecision(None, "local_transport_ambiguous")
    return AutomaticTransportDecision(next(iter(transports)), "model_family")


@dataclass(frozen=True, slots=True)
class NativeWriteAuthoritySnapshot:
    """Current single-writer lease; a lease is never transferable."""

    device_id: str | None
    transport: ZendureTransport | None
    generation: int
    synchronized: bool
    reason: str
    changed_at: datetime


class NativeTransportRouter:
    """Own exactly one synchronized native writer without runtime fallback."""

    def __init__(self) -> None:
        self._snapshot = NativeWriteAuthoritySnapshot(
            None,
            None,
            0,
            False,
            "not_configured",
            datetime.now(timezone.utc),
        )

    @property
    def snapshot(self) -> NativeWriteAuthoritySnapshot:
        return self._snapshot

    def select(
        self,
        device_id: str | None,
        transport: ZendureTransport | None,
    ) -> NativeWriteAuthoritySnapshot:
        """Select an authority but require fresh synchronization before writes."""

        if (
            self._snapshot.device_id == device_id
            and self._snapshot.transport is transport
        ):
            return self._snapshot
        self._snapshot = NativeWriteAuthoritySnapshot(
            device_id,
            transport,
            self._snapshot.generation + 1,
            False,
            "awaiting_synchronization" if transport is not None else "not_selected",
            datetime.now(timezone.utc),
        )
        return self._snapshot

    def update_readiness(self, *, ready: bool, reason: str) -> None:
        """Grant or revoke the selected writer after current-state validation."""

        synchronized = bool(ready and self._snapshot.transport is not None)
        if (
            self._snapshot.synchronized == synchronized
            and self._snapshot.reason == reason
        ):
            return
        generation = self._snapshot.generation
        if self._snapshot.synchronized and not synchronized:
            # Invalidates every authorization issued before disconnect/staleness.
            generation += 1
        self._snapshot = NativeWriteAuthoritySnapshot(
            self._snapshot.device_id,
            self._snapshot.transport,
            generation,
            synchronized,
            reason,
            datetime.now(timezone.utc),
        )

    async def execute(
        self,
        *,
        device_id: str,
        transport: ZendureTransport,
        generation: int,
        command: Any,
        sender: NativeTransportSender,
    ) -> Any:
        """Execute once only when the exact current writer lease still matches."""

        authority = self._snapshot
        if not authority.synchronized:
            raise RuntimeError("write_authority_not_synchronized")
        if authority.device_id != device_id:
            raise RuntimeError("write_authority_device_mismatch")
        if authority.transport is not transport:
            raise RuntimeError("write_authority_transport_mismatch")
        if authority.generation != generation:
            raise RuntimeError("write_authority_superseded")
        return await sender(command)

    def diagnostics(self) -> dict[str, Any]:
        """Expose bounded state without physical identities or credentials."""

        value = self._snapshot
        return {
            "selected": value.transport is not None,
            "transport": value.transport.value if value.transport else None,
            "generation": value.generation,
            "synchronized": value.synchronized,
            "reason": value.reason,
            "changed_at": value.changed_at,
        }

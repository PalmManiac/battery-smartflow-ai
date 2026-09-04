"""Transport-neutral native command verification contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import ZendureTransport  # noqa: E402
from custom_components.battery_smartflow_ai.native_command_verification import (  # noqa: E402
    CommandVerificationStatus,
    EffectStatus,
    NativeCommandVerificationManager,
    ReadbackPolicy,
)


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def prepared(manager, *, device="private-device-a", target="output_limit",
             expected=100.0, tolerance=0.0, at=NOW, max_attempts=1):
    return manager.prepare(
        device_id=device, command_type="set_output_limit", target_key=target,
        transport=ZendureTransport.ZENSDK, requested_value=expected,
        final_value=expected,
        readback=ReadbackPolicy("outputLimit", expected, tolerance),
        prepared_at=at, max_attempts=max_attempts,
    )


def sent(manager, command):
    manager.gate(command.command_id, accepted=True, at=NOW + timedelta(milliseconds=10))
    manager.sent(command.command_id, at=NOW + timedelta(milliseconds=20))
    manager.transport_result(
        command.command_id, ok=True, status="http_200",
        at=NOW + timedelta(milliseconds=40),
    )


class NativeCommandVerificationTests(unittest.TestCase):
    def test_transport_ok_readback_and_effect_are_distinct(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager)
        sent(manager, command)
        self.assertEqual(command.status, CommandVerificationStatus.TRANSPORT_OK)
        self.assertTrue(manager.observe_readback(
            command.command_id, device_id="private-device-a",
            property_name="outputLimit", value=100,
            observed_at=NOW + timedelta(milliseconds=120),
        ))
        self.assertEqual(command.status, CommandVerificationStatus.READBACK_CONFIRMED)
        manager.effect(
            command.command_id, status=EffectStatus.CONFIRMED,
            at=NOW + timedelta(milliseconds=250),
        )
        self.assertEqual(command.status, CommandVerificationStatus.EFFECT_CONFIRMED)
        self.assertEqual(command.diagnostics()["send_to_readback_seconds"], 0.1)
        self.assertEqual(command.diagnostics()["send_to_effect_seconds"], 0.23)

    def test_stale_wrong_device_and_wrong_property_never_confirm(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager)
        sent(manager, command)
        for device, prop, observed in (
            ("private-device-a", "outputLimit", NOW),
            ("private-device-b", "outputLimit", NOW + timedelta(seconds=1)),
            ("private-device-a", "inputLimit", NOW + timedelta(seconds=1)),
        ):
            self.assertFalse(manager.observe_readback(
                command.command_id, device_id=device, property_name=prop,
                value=100, observed_at=observed,
            ))
        self.assertEqual(command.status, CommandVerificationStatus.TRANSPORT_OK)

    def test_tolerance_accepts_quantized_readback(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager, expected=101, tolerance=2)
        sent(manager, command)
        self.assertTrue(manager.observe_readback(
            command.command_id, device_id="private-device-a",
            property_name="outputLimit", value=100,
            observed_at=NOW + timedelta(seconds=1),
        ))

    def test_mismatch_contradiction_and_timeouts_are_distinct(self):
        manager = NativeCommandVerificationManager()
        mismatch = prepared(manager)
        sent(manager, mismatch)
        manager.observe_readback(
            mismatch.command_id, device_id="private-device-a",
            property_name="outputLimit", value=90,
            observed_at=NOW + timedelta(seconds=1),
        )
        self.assertEqual(mismatch.status, CommandVerificationStatus.READBACK_MISMATCH)
        manager.observe_readback(
            mismatch.command_id, device_id="private-device-a",
            property_name="outputLimit", value=80,
            observed_at=NOW + timedelta(seconds=2),
        )
        self.assertEqual(mismatch.status, CommandVerificationStatus.CONTRADICTORY_RESPONSE)

        timeout = prepared(manager, target="input_limit")
        sent(manager, timeout)
        manager.readback_timeout(timeout.command_id)
        self.assertEqual(timeout.status, CommandVerificationStatus.READBACK_TIMEOUT)

    def test_effect_not_observable_is_not_failure(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager)
        sent(manager, command)
        manager.observe_readback(
            command.command_id, device_id="private-device-a",
            property_name="outputLimit", value=100,
            observed_at=NOW + timedelta(seconds=1),
        )
        manager.effect(command.command_id, status=EffectStatus.NOT_OBSERVABLE)
        self.assertEqual(command.status, CommandVerificationStatus.READBACK_CONFIRMED)
        self.assertEqual(command.effect_status, EffectStatus.NOT_OBSERVABLE)

    def test_transport_error_followed_by_applied_value_is_contradictory(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager)
        manager.gate(command.command_id, accepted=True, at=NOW)
        manager.sent(command.command_id, at=NOW + timedelta(milliseconds=10))
        manager.transport_result(
            command.command_id, ok=False, status="timeout",
            at=NOW + timedelta(seconds=1),
        )
        self.assertFalse(manager.observe_readback(
            command.command_id, device_id="private-device-a",
            property_name="outputLimit", value=100,
            observed_at=NOW + timedelta(seconds=2),
        ))
        self.assertEqual(
            command.status, CommandVerificationStatus.CONTRADICTORY_RESPONSE
        )
        self.assertEqual(
            command.reason, "transport_error_but_readback_confirmed"
        )

    def test_newer_same_target_supersedes_only_matching_device_target(self):
        manager = NativeCommandVerificationManager()
        old = prepared(manager)
        sent(manager, old)
        other_device = prepared(manager, device="private-device-b")
        other_target = prepared(manager, target="input_limit")
        new = prepared(manager, expected=80)
        self.assertEqual(old.status, CommandVerificationStatus.SUPERSEDED)
        self.assertEqual(old.superseded_by, new.command_id)
        self.assertEqual(other_device.status, CommandVerificationStatus.PREPARED)
        self.assertEqual(other_target.status, CommandVerificationStatus.PREPARED)
        self.assertFalse(manager.observe_readback(
            old.command_id, device_id="private-device-a",
            property_name="outputLimit", value=100,
            observed_at=NOW + timedelta(seconds=1),
        ))

    def test_retry_limit_and_cancel_before_send_are_enforced(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager)
        manager.gate(command.command_id, accepted=True)
        manager.sent(command.command_id)
        with self.assertRaisesRegex(ValueError, "gate accepted"):
            manager.sent(command.command_id)
        cancellable = prepared(manager, target="mode")
        manager.cancel(cancellable.command_id)
        self.assertEqual(cancellable.status, CommandVerificationStatus.CANCELLED)

    def test_effect_timeout_and_mismatch_are_failures(self):
        manager = NativeCommandVerificationManager()
        for index, effect in enumerate((EffectStatus.TIMEOUT, EffectStatus.MISMATCH)):
            command = prepared(manager, target=f"target-{index}")
            sent(manager, command)
            manager.observe_readback(
                command.command_id, device_id="private-device-a",
                property_name="outputLimit", value=100,
                observed_at=NOW + timedelta(seconds=1),
            )
            manager.effect(command.command_id, status=effect)
        self.assertEqual(
            manager.diagnostics()["failures_by_device"].popitem()[1], 2
        )

    def test_history_is_bounded_without_removing_active_commands(self):
        manager = NativeCommandVerificationManager(history_limit=2)
        active = prepared(manager, target="active")
        for index in range(3):
            command = prepared(manager, target=f"done-{index}")
            manager.cancel(command.command_id)
        commands = manager.diagnostics()["commands"]
        self.assertEqual(len(commands), 2)
        self.assertIn(active.command_id, {item["command_id"] for item in commands})

    def test_diagnostics_pseudonymize_devices_and_exclude_secrets(self):
        manager = NativeCommandVerificationManager()
        command = prepared(manager, device="serial-and-token-secret")
        manager.gate(command.command_id, accepted=False, reasons=("hems_active",))
        diagnostics = manager.diagnostics()
        text = str(diagnostics)
        self.assertNotIn("serial-and-token-secret", text)
        self.assertIn("device_", text)
        self.assertNotIn("metadata", text)


if __name__ == "__main__":
    unittest.main()

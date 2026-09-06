"""Model-specific, privacy-safe transport metrics tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (
    ZendureTransport,  # noqa: E402
)
from custom_components.battery_smartflow_ai.native_command_verification import (  # noqa: E402
    EffectStatus,
    NativeCommandVerificationManager,
    ReadbackPolicy,
)
from custom_components.battery_smartflow_ai.native_transport_metrics import (  # noqa: E402
    NativeTransportMetrics,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
DEVICE = "private-serial-and-device-key"


def completed_command(
    manager: NativeCommandVerificationManager,
    *,
    index: int,
):
    prepared_at = NOW + timedelta(seconds=index * 2)
    command = manager.prepare(
        device_id=DEVICE,
        command_type="outputLimit",
        target_key=f"outputLimit-{index}",
        transport=ZendureTransport.ZENSDK,
        requested_value=100 + index,
        final_value=100 + index,
        readback=ReadbackPolicy("outputLimit", 100 + index),
        prepared_at=prepared_at,
    )
    manager.gate(
        command.command_id,
        accepted=True,
        at=prepared_at + timedelta(milliseconds=10),
    )
    manager.sent(
        command.command_id,
        at=prepared_at + timedelta(milliseconds=20),
    )
    manager.transport_result(
        command.command_id,
        ok=True,
        status="http_200",
        at=prepared_at + timedelta(milliseconds=40),
    )
    manager.observe_readback(
        command.command_id,
        device_id=DEVICE,
        property_name="outputLimit",
        value=100 + index,
        observed_at=prepared_at + timedelta(milliseconds=120 + index),
    )
    manager.effect(
        command.command_id,
        status=EffectStatus.CONFIRMED,
        at=prepared_at + timedelta(milliseconds=220 + index),
    )
    return command


class NativeTransportMetricsTests(unittest.TestCase):
    def test_command_latencies_are_grouped_by_model_firmware_and_transport(self):
        manager = NativeCommandVerificationManager(history_limit=30)
        metrics = NativeTransportMetrics()
        metrics.register_device(
            DEVICE,
            model="SolarFlow 2400 AC",
            firmware="1.2.3",
        )
        for index in range(20):
            completed_command(manager, index=index)

        group = metrics.export(manager.measurements())["command_groups"][0]

        self.assertEqual(group["model"], "SolarFlow 2400 AC")
        self.assertEqual(group["firmware"], "1.2.3")
        self.assertEqual(group["transport"], "zensdk")
        self.assertEqual(group["sample_count"], 20)
        self.assertEqual(group["timeout_rate"], 0.0)
        self.assertEqual(group["transport_error_rate"], 0.0)
        self.assertEqual(group["latency_seconds"]["send_to_readback"]["count"], 20)
        self.assertIsNotNone(group["latency_seconds"]["send_to_readback"]["p95"])

    def test_small_samples_do_not_claim_percentile_precision(self):
        manager = NativeCommandVerificationManager()
        metrics = NativeTransportMetrics()
        completed_command(manager, index=0)

        stats = metrics.export(manager.measurements())["command_groups"][0][
            "latency_seconds"
        ]["send_to_readback"]

        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["median"], 0.1)
        self.assertIsNone(stats["p90"])
        self.assertIsNone(stats["p95"])

    def test_telemetry_interval_and_reconnects_are_separate(self):
        metrics = NativeTransportMetrics()
        metrics.register_device(DEVICE, model="Hyper 2000")
        metrics.observe_connection(
            device_id=DEVICE,
            transport=ZendureTransport.LOCAL_MQTT,
            connected=True,
        )
        metrics.observe_connection(
            device_id=DEVICE,
            transport=ZendureTransport.LOCAL_MQTT,
            connected=False,
        )
        metrics.observe_connection(
            device_id=DEVICE,
            transport=ZendureTransport.LOCAL_MQTT,
            connected=True,
        )
        for offset in (0, 2, 5):
            metrics.observe_telemetry(
                device_id=DEVICE,
                transport=ZendureTransport.LOCAL_MQTT,
                observed_at=NOW + timedelta(seconds=offset),
            )

        group = metrics.export(())["telemetry_groups"][0]

        self.assertEqual(group["disconnect_count"], 1)
        self.assertEqual(group["reconnect_count"], 1)
        self.assertEqual(group["update_interval_seconds"]["median"], 2.5)

    def test_export_pseudonymizes_identity_and_contains_no_secrets(self):
        manager = NativeCommandVerificationManager()
        metrics = NativeTransportMetrics()
        metrics.register_device(
            DEVICE,
            model="SolarFlow 2400 AC",
            firmware="1.2.3",
        )
        completed_command(manager, index=0)

        exported = repr(metrics.export(manager.measurements()))

        self.assertNotIn(DEVICE, exported)
        self.assertNotIn("token", exported.lower())
        self.assertNotIn("password", exported.lower())
        self.assertIn("device_", exported)


if __name__ == "__main__":
    unittest.main()

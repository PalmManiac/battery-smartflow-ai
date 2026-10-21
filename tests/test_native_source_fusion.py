"""Source-separated native Zendure normalization tests."""

from __future__ import annotations

import json
import unittest
from base64 import b64encode
from datetime import datetime, timedelta, timezone

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud_mqtt import (
    CloudMqttMessage,
)
from custom_components.battery_smartflow_ai.native_source_fusion import (
    NativeSourceFusion,
)


class Response:
    def __init__(self, value):
        self.value = value

    async def json(self):
        return self.value


async def make_bootstrap(device_ids=("device-1",), product_model="SolarFlow2400AC"):
    token = b64encode(b"https://api.example.com.app-secret").decode()

    async def post(*_args, **_kwargs):
        return Response({
            "code": 200,
            "success": True,
            "data": {
                "deviceList": [
                    {
                        "deviceKey": device_id,
                        "productKey": "product-1",
                        "productModel": product_model,
                        "online": True,
                    }
                    for device_id in device_ids
                ],
                "mqtt": {
                    "clientId": "secret", "url": "mqtt://broker:1883",
                    "username": "secret", "password": "secret",
                },
            },
        })

    return await ZendureCloudClient(post).async_discover(token)


def report(
    at,
    properties,
    *,
    transport="cloud_mqtt",
    device_id="device-1",
    packs=None,
    retained=False,
):
    payload = {"properties": properties}
    if packs is not None:
        payload["packData"] = packs
    return CloudMqttMessage(
        received_at=at,
        topic=f"/product-1/{device_id}/properties/report",
        payload=json.dumps(payload).encode(),
        parsed_payload=payload,
        payload_format="json",
        device_candidate_id=f"cloud_mqtt:{device_id}",
        pack_id=None,
        known_topic=True,
        session_number=1,
        transport=transport,
        retained=retained,
    )


def error_event(at, *, data=None, off_data=0):
    payload = {"offData": off_data, "eventId": 3, "data": data or []}
    return CloudMqttMessage(
        received_at=at,
        topic="/product-1/device-1/event/error",
        payload=json.dumps(payload).encode(),
        parsed_payload=payload,
        payload_format="json",
        device_candidate_id="cloud_mqtt:device-1",
        pack_id=None,
        known_topic=False,
        session_number=1,
        transport="cloud_mqtt",
        retained=False,
    )


class NativeSourceFusionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        self.fusion = NativeSourceFusion(await make_bootstrap())

    def test_priority_is_independent_of_callback_order(self):
        cloud = report(self.now, {"electricLevel": 50}, transport="cloud_mqtt")
        zensdk = report(self.now, {"electricLevel": 51}, transport="zensdk")
        self.fusion.apply(zensdk)
        state = self.fusion.apply(cloud).state
        self.assertEqual(state.soc_pct.value, 51.0)
        self.assertEqual(state.observed_transport, ZendureTransport.ZENSDK)

    async def test_configured_transport_preference_is_per_device(self):
        fusion = NativeSourceFusion(
            await make_bootstrap(("device-1", "device-2")),
            preferred_transport=ZendureTransport.ZENSDK,
            preferred_transports={
                "cloud_mqtt:device-1": ZendureTransport.CLOUD_MQTT,
            },
        )

        fusion.apply(report(self.now, {"electricLevel": 50}, transport="zensdk"))
        state = fusion.apply(
            report(self.now, {"electricLevel": 51}, transport="cloud_mqtt")
        ).state
        fusion.apply(
            report(
                self.now,
                {"electricLevel": 50},
                transport="cloud_mqtt",
                device_id="device-2",
            )
        )
        other_state = fusion.apply(
            report(
                self.now,
                {"electricLevel": 51},
                transport="zensdk",
                device_id="device-2",
            )
        ).state

        self.assertEqual(state.soc_pct.value, 51.0)
        self.assertEqual(state.observed_transport, ZendureTransport.CLOUD_MQTT)
        self.assertEqual(other_state.soc_pct.value, 51.0)
        self.assertEqual(other_state.observed_transport, ZendureTransport.ZENSDK)

    def test_debug_snapshot_keeps_raw_main_and_pack_properties_per_transport(self):
        self.fusion.apply(
            report(
                self.now,
                {"electricLevel": 50, "futureMainSensor": 17.5},
                transport="zensdk",
                packs=[{"sn": "pack-1", "futurePackSensor": "active"}],
            )
        )

        snapshot = self.fusion.debug_property_snapshot("cloud_mqtt:device-1")

        self.assertEqual(
            snapshot["zensdk"]["main_properties"]["futureMainSensor"], 17.5
        )
        self.assertEqual(
            snapshot["zensdk"]["packs"][0]["properties"]["futurePackSensor"],
            "active",
        )

    def test_fresh_cloud_value_replaces_stale_zensdk_value(self):
        self.fusion.apply(report(self.now, {"electricLevel": 40}, transport="zensdk"))
        later = self.now + timedelta(seconds=91)
        state = self.fusion.apply(
            report(later, {"electricLevel": 42}, transport="cloud_mqtt")
        ).state
        self.assertEqual(state.soc_pct.value, 42.0)
        self.assertEqual(state.observed_transport, ZendureTransport.CLOUD_MQTT)

    def test_safety_conflict_is_invalid(self):
        self.fusion.apply(report(self.now, {"hemsState": 0}, transport="zensdk"))
        state = self.fusion.apply(
            report(self.now, {"hemsState": 1}, transport="cloud_mqtt")
        ).state
        self.assertEqual(state.hems_active.validity, ValueValidity.INVALID)
        self.assertIsNone(state.hems_active.value)

    def test_cloud_error_snapshot_prevents_false_protection_conflict(self):
        """Match the SF2400AC Cloud plus ZenSDK startup sequence."""
        self.fusion.apply(
            report(
                self.now,
                {"faultLevel": 2, "is_error": 0},
                transport="zensdk",
            )
        )
        conflict = self.fusion.apply(
            report(
                self.now + timedelta(milliseconds=1),
                {"faultLevel": 2},
                transport="cloud_mqtt",
            )
        ).state
        self.assertEqual(
            conflict.protection_active.validity,
            ValueValidity.INVALID,
        )

        resolved = self.fusion.apply(
            error_event(self.now + timedelta(milliseconds=2))
        ).state
        self.assertTrue(resolved.protection_active.valid)
        self.assertFalse(resolved.protection_active.value)

    def test_small_soc_difference_is_allowed_but_large_conflict_blocks(self):
        self.fusion.apply(
            report(self.now, {"electricLevel": 50}, transport="cloud_mqtt")
        )
        plausible = self.fusion.apply(
            report(self.now, {"electricLevel": 52}, transport="zensdk")
        ).state
        self.assertTrue(plausible.soc_pct.valid)
        conflicting = self.fusion.apply(
            report(
                self.now + timedelta(seconds=1),
                {"electricLevel": 70},
                transport="zensdk",
            )
        ).state
        self.assertEqual(conflicting.soc_pct.validity, ValueValidity.INVALID)

    def test_conflicting_fresh_modes_block_selection(self):
        self.fusion.apply(
            report(self.now, {"acMode": 1}, transport="cloud_mqtt")
        )
        state = self.fusion.apply(
            report(self.now, {"acMode": 2}, transport="zensdk")
        ).state
        self.assertEqual(state.mode.validity, ValueValidity.INVALID)

    def test_pack_properties_are_fused_and_zero_remains_valid(self):
        self.fusion.apply(report(
            self.now,
            {},
            transport="cloud_mqtt",
            packs=[{"sn": "PACK-1", "packType": 5, "socLevel": 75, "power": 0, "state": 0}],
        ))
        result = self.fusion.apply(report(
            self.now,
            {},
            transport="zensdk",
            packs=[{"sn": "PACK-1", "packType": 5, "socLevel": 76, "power": 0, "state": 0}],
        ))
        pack = result.state.packs[0]
        self.assertEqual(pack.serial_number, "PACK-1")
        self.assertEqual(pack.soc_pct.value, 76.0)
        self.assertEqual(pack.charge_power_w.value, 0.0)
        self.assertTrue(pack.charge_power_w.valid)

    def test_complete_pack_report_retires_old_identity_across_transports(self):
        for transport in ("cloud_mqtt", "zensdk"):
            self.fusion.apply(
                report(
                    self.now,
                    {},
                    transport=transport,
                    packs=[{"sn": "old-pack", "packType": 5, "socLevel": 70}],
                )
            )

        replacement = self.fusion.apply(
            report(
                self.now + timedelta(minutes=5),
                {},
                transport="cloud_mqtt",
                packs=[{"sn": "new-pack", "packType": 5, "socLevel": 65}],
            )
        )

        self.assertEqual(
            [pack.pack_id for pack in replacement.state.packs], ["new-pack"]
        )

    async def test_hyper_pack_membership_requires_confirmed_changes(self):
        fusion = NativeSourceFusion(
            await make_bootstrap(product_model="Hyper 2000")
        )
        both_packs = [
            {"sn": "pack-a", "packType": 5, "socLevel": 70},
            {"sn": "pack-b", "packType": 5, "socLevel": 68},
        ]
        only_first_pack = [
            {"sn": "pack-a", "packType": 5, "socLevel": 70},
        ]

        fusion.apply(report(self.now, {}, packs=both_packs))
        transient = fusion.apply(
            report(
                self.now + timedelta(seconds=1),
                {},
                packs=only_first_pack,
            )
        )
        self.assertEqual(
            {pack.pack_id for pack in transient.state.packs},
            {"pack-a", "pack-b"},
        )

        fusion.apply(
            report(self.now + timedelta(seconds=2), {}, packs=both_packs)
        )
        fusion.apply(
            report(
                self.now + timedelta(seconds=3),
                {},
                packs=only_first_pack,
            )
        )
        confirmed_removal = fusion.apply(
            report(
                self.now + timedelta(seconds=4),
                {},
                packs=only_first_pack,
            )
        )
        self.assertEqual(
            [pack.pack_id for pack in confirmed_removal.state.packs], ["pack-a"]
        )

    async def test_hyper_pack_addition_is_hidden_until_confirmed(self):
        fusion = NativeSourceFusion(
            await make_bootstrap(product_model="Hyper 2000")
        )
        one_pack = [{"sn": "pack-a", "packType": 5, "socLevel": 70}]
        two_packs = [
            {"sn": "pack-a", "packType": 5, "socLevel": 70},
            {"sn": "pack-b", "packType": 5, "socLevel": 68},
        ]

        initial = fusion.apply(
            report(self.now, {}, packs=one_pack)
        )
        self.assertEqual(
            [pack.pack_id for pack in initial.state.packs], ["pack-a"]
        )

        transient_addition = fusion.apply(
            report(self.now + timedelta(seconds=1), {}, packs=two_packs)
        )
        self.assertEqual(
            [pack.pack_id for pack in transient_addition.state.packs], ["pack-a"]
        )
        confirmed_addition = fusion.apply(
            report(self.now + timedelta(seconds=2), {}, packs=two_packs)
        )
        self.assertEqual(
            {pack.pack_id for pack in confirmed_addition.state.packs},
            {"pack-a", "pack-b"},
        )

    def test_diagnostics_contain_selection_not_values(self):
        self.fusion.apply(report(self.now, {"electricLevel": 50}, transport="zensdk"))
        diagnostics = self.fusion.source_diagnostics("cloud_mqtt:device-1")
        self.assertEqual(diagnostics["soc_pct"]["transport"], "zensdk")
        self.assertNotIn("value", diagnostics["soc_pct"])

    def test_retained_message_cannot_override_fresh_cloud_value(self):
        self.fusion.apply(
            report(self.now, {"electricLevel": 44}, transport="cloud_mqtt")
        )
        result = self.fusion.apply(
            report(
                self.now + timedelta(seconds=1),
                {"electricLevel": 99},
                transport="zensdk",
                retained=True,
            )
        )
        self.assertEqual(result.state.soc_pct.value, 44.0)
        diagnostics = self.fusion.source_diagnostics(
            "cloud_mqtt:device-1",
            now=self.now + timedelta(seconds=1),
        )["soc_pct"]
        self.assertEqual(diagnostics["transport"], "cloud_mqtt")
        zensdk = next(
            item for item in diagnostics["sources"]
            if item["transport"] == "zensdk"
        )
        self.assertTrue(zensdk["retained"])
        self.assertEqual(zensdk["age_seconds"], 0.0)

    def test_selected_at_changes_only_when_selected_source_changes(self):
        self.fusion.apply(
            report(self.now, {"electricLevel": 40}, transport="cloud_mqtt")
        )
        first = self.fusion.source_diagnostics(
            "cloud_mqtt:device-1", now=self.now
        )["soc_pct"]["selected_at"]
        self.fusion.snapshot(
            "cloud_mqtt:device-1", now=self.now + timedelta(seconds=1)
        )
        unchanged = self.fusion.source_diagnostics(
            "cloud_mqtt:device-1", now=self.now + timedelta(seconds=1)
        )["soc_pct"]["selected_at"]
        self.fusion.apply(
            report(
                self.now + timedelta(seconds=2),
                {"electricLevel": 41},
                transport="zensdk",
            )
        )
        changed = self.fusion.source_diagnostics(
            "cloud_mqtt:device-1", now=self.now + timedelta(seconds=2)
        )["soc_pct"]["selected_at"]
        self.assertEqual(first, unchanged)
        self.assertGreater(changed, unchanged)


class NativeReadToleranceTests(unittest.TestCase):
    def test_numeric_tolerance_avoids_false_safety_conflict(self):
        from custom_components.battery_smartflow_ai.core.models import MeasuredValue
        from custom_components.battery_smartflow_ai.native_read_source import (
            NativeReadSourceArbiter,
            SourceMeasurement,
        )

        selected = NativeReadSourceArbiter().select(
            "soc_pct",
            (
                SourceMeasurement(ZendureTransport.ZENSDK, MeasuredValue.available(50.0)),
                SourceMeasurement(ZendureTransport.CLOUD_MQTT, MeasuredValue.available(51.0)),
            ),
            safety_critical=True,
            conflict_tolerance=2.0,
        )
        self.assertTrue(selected.measurement.valid)


if __name__ == "__main__":
    unittest.main()

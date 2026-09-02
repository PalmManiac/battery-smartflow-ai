"""Transport-neutral native Zendure state normalization tests."""

from __future__ import annotations

from base64 import b64encode
from dataclasses import fields
from datetime import datetime, timedelta, timezone
import json
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    DeviceOperatingMode,
    NeutralDeviceState,
    ValueValidity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.zendure_cloud import (  # noqa: E402
    ZendureCloudClient,
)
from custom_components.battery_smartflow_ai.zendure_cloud_mqtt import (  # noqa: E402
    CloudMqttMessage,
)
from custom_components.battery_smartflow_ai.zendure_normalizer import (  # noqa: E402
    MAIN_PROPERTY_MAPPINGS,
    PACK_PROPERTY_MAPPINGS,
    MappingScope,
    ZendureCloudNormalizer,
)
from custom_components.battery_smartflow_ai.zendure_initial_sync import (  # noqa: E402
    ZendureInitialSyncRecorder,
)


class Response:
    def __init__(self, value):
        self.value = value

    async def json(self):
        return self.value


async def make_bootstrap():
    token = b64encode(b"https://api.example.com.app-secret").decode()

    async def post(*_args, **_kwargs):
        return Response(
            {
                "code": 200,
                "success": True,
                "data": {
                    "deviceList": [
                        {
                            "deviceKey": "device-1",
                            "productKey": "product-1",
                            "productModel": "SolarFlow2400AC",
                            "deviceName": "Primary",
                            "online": True,
                        },
                        {
                            "deviceKey": "device-2",
                            "productKey": "product-2",
                            "productModel": "SolarFlow800Pro",
                            "deviceName": "Secondary",
                            "online": True,
                        },
                    ],
                    "mqtt": {
                        "clientId": "client-secret",
                        "url": "mqtts://broker.secret:8883",
                        "username": "user-secret",
                        "password": "password-secret",
                    },
                },
            }
        )

    return await ZendureCloudClient(post).async_discover(token)


def report(at, payload, *, device="device-1", topic="properties/report"):
    raw = json.dumps(payload).encode()
    return CloudMqttMessage(
        received_at=at,
        topic=f"/product-1/{device}/{topic}",
        payload=raw,
        parsed_payload=payload,
        payload_format="json",
        device_candidate_id=f"cloud_mqtt:{device}",
        pack_id=None,
        known_topic=True,
        session_number=1,
    )


class ZendureNormalizerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bootstrap = await make_bootstrap()
        self.at = datetime(2026, 9, 2, 15, 0, tzinfo=timezone.utc)

    def full_payload(self):
        return {
            "properties": {
                "electricLevel": 55,
                "outputPackPower": 276,
                "packInputPower": 0,
                "gridInputPower": 279,
                "outputHomePower": 0,
                "solarInputPower": 620,
                "acMode": 1,
                "inputLimit": 279,
                "outputLimit": 0,
                "chargeMaxLimit": 2400,
                "inverseMaxPower": 1800,
                "minSoc": 100,
                "socSet": 930,
                "hemsState": 0,
                "faultLevel": 0,
                "heatState": 0,
                "hyperTmp": 2961,
                "BatVolt": 4953,
                "masterSoftVersion": 4106,
                "futureProperty": {"kept": "only in raw diagnostics"},
            },
            "packData": [
                {
                    "sn": "pack-a",
                    "packType": 5,
                    "socLevel": 54,
                    "state": 1,
                    "power": 227,
                    "maxTemp": 2961,
                    "totalVol": 4940,
                    "batcur": 46,
                    "maxVol": 330,
                    "minVol": 329,
                    "softVersion": 4106,
                    "heatState": 0,
                    "futurePackProperty": 123,
                },
                {
                    "sn": "pack-b",
                    "packType": 300,
                    "socLevel": 56,
                    "state": 2,
                    "power": 19,
                    "maxTemp": 2941,
                    "totalVol": 4930,
                    "batcur": 65532,
                    "maxVol": 329,
                    "minVol": 328,
                    "softVersion": 4123,
                },
            ],
        }

    async def test_complete_main_and_mixed_pack_state(self):
        result = ZendureCloudNormalizer(self.bootstrap).apply(
            report(self.at, self.full_payload())
        )
        self.assertIsNotNone(result)
        state = result.state
        self.assertIsInstance(state, NeutralDeviceState)
        self.assertEqual(state.observed_transport, ZendureTransport.CLOUD_MQTT)
        self.assertEqual(state.soc_pct.value, 55.0)
        self.assertEqual(state.charge_power_w.value, 276.0)
        self.assertEqual(state.discharge_power_w.value, 0.0)
        self.assertEqual(state.ac_input_power_w.value, 279.0)
        self.assertEqual(state.ac_output_power_w.value, 0.0)
        self.assertEqual(state.pv_power_w.value, 620.0)
        self.assertEqual(state.mode.value, DeviceOperatingMode.CHARGE)
        self.assertEqual(state.setpoints.input_limit_w.value, 279.0)
        self.assertEqual(state.setpoints.output_limit_w.value, 0.0)
        self.assertEqual(state.setpoints.min_soc_pct.value, 10.0)
        self.assertEqual(state.setpoints.max_soc_pct.value, 93.0)
        self.assertFalse(state.hems_active.value)
        self.assertAlmostEqual(state.temperature_c.value, 22.95)
        self.assertEqual(state.battery_voltage_v.value, 49.53)
        self.assertEqual(state.firmware.value, "4106")
        self.assertEqual(len(state.packs), 2)
        first, second = state.packs
        self.assertEqual(first.pack_id, "pack-a")
        self.assertEqual(first.parent_system_id, state.system_id)
        self.assertEqual(first.charge_power_w.value, 227.0)
        self.assertEqual(first.discharge_power_w.value, 0.0)
        self.assertEqual(first.voltage_v.value, 49.4)
        self.assertEqual(first.current_a.value, 4.6)
        self.assertEqual(first.cell_min_v.value, 3.29)
        self.assertEqual(first.cell_max_v.value, 3.3)
        self.assertEqual(second.charge_power_w.value, 0.0)
        self.assertEqual(second.discharge_power_w.value, 19.0)
        self.assertEqual(second.current_a.value, -0.4)
        self.assertEqual(result.unknown_main_properties, ("futureProperty",))
        self.assertEqual(
            result.unknown_pack_properties, ("futurePackProperty",)
        )

    async def test_incremental_update_preserves_previous_values_and_valid_zero(self):
        normalizer = ZendureCloudNormalizer(self.bootstrap)
        normalizer.apply(report(self.at, self.full_payload()))
        result = normalizer.apply(
            report(
                self.at + timedelta(seconds=5),
                {"properties": {"electricLevel": 0, "inputLimit": 0}},
            )
        )
        self.assertEqual(result.state.soc_pct.value, 0.0)
        self.assertTrue(result.state.soc_pct.valid)
        self.assertEqual(result.state.setpoints.input_limit_w.value, 0.0)
        self.assertEqual(result.state.pv_power_w.value, 620.0)
        self.assertEqual(
            result.state.pv_power_w.observed_at,
            self.at,
        )

    async def test_missing_invalid_unsupported_stale_and_offline_are_distinct(self):
        system_id = "cloud_mqtt:device-1"
        normalizer = ZendureCloudNormalizer(
            self.bootstrap,
            stale_after_seconds=10,
            supported_device_targets={
                system_id: frozenset({"soc_pct", "pv_power_w"})
            },
        )
        initial = normalizer.snapshot(system_id, now=self.at)
        self.assertEqual(
            initial.state.soc_pct.validity,
            ValueValidity.NEVER_RECEIVED,
        )
        self.assertEqual(
            initial.state.hems_active.validity,
            ValueValidity.UNSUPPORTED,
        )
        invalid = normalizer.apply(
            report(self.at, {"properties": {"electricLevel": "55"}})
        )
        self.assertEqual(invalid.state.soc_pct.validity, ValueValidity.INVALID)
        normalizer.apply(
            report(self.at, {"properties": {"electricLevel": 55}})
        )
        stale = normalizer.snapshot(
            system_id, now=self.at + timedelta(seconds=11)
        )
        self.assertEqual(stale.state.soc_pct.value, 55.0)
        self.assertEqual(stale.state.soc_pct.validity, ValueValidity.STALE)
        normalizer.set_online(system_id, False)
        offline = normalizer.snapshot(system_id, now=self.at)
        self.assertEqual(offline.state.soc_pct.value, 55.0)
        self.assertEqual(offline.state.soc_pct.validity, ValueValidity.OFFLINE)
        self.assertFalse(offline.state.online.value)

    async def test_out_of_range_and_non_finite_values_are_invalid(self):
        normalizer = ZendureCloudNormalizer(self.bootstrap)
        invalid = normalizer.apply(
            report(
                self.at,
                {
                    "properties": {
                        "electricLevel": 101,
                        "solarInputPower": float("inf"),
                    }
                },
            )
        )
        self.assertEqual(invalid.state.soc_pct.validity, ValueValidity.INVALID)
        self.assertEqual(invalid.state.pv_power_w.validity, ValueValidity.INVALID)

    async def test_hems_energy_topic_is_observed_as_blocker_input_only(self):
        normalizer = ZendureCloudNormalizer(self.bootstrap)
        result = normalizer.apply(
            report(self.at, {}, topic="properties/energy")
        )
        self.assertTrue(result.state.hems_active.value)
        self.assertTrue(result.state.hems_active.valid)

    async def test_unknown_device_message_is_not_guessed(self):
        normalizer = ZendureCloudNormalizer(self.bootstrap)
        unknown = report(self.at, self.full_payload(), device="not-discovered")
        self.assertIsNone(normalizer.apply(unknown))

    async def test_mapping_contract_records_units_scale_sign_type_and_scope(self):
        min_soc = MAIN_PROPERTY_MAPPINGS["minSoc"]
        current = PACK_PROPERTY_MAPPINGS["batcur"]
        self.assertEqual(min_soc.target, "min_soc_pct")
        self.assertEqual(min_soc.scale, 0.1)
        self.assertEqual(min_soc.scope, MappingScope.MAIN)
        self.assertEqual(current.raw_types, (int,))
        self.assertEqual(current.raw_unit, "0.1 A signed16")
        self.assertEqual(current.target_unit, "A")
        self.assertEqual(current.sign, "signed")

    async def test_neutral_models_have_no_credentials_or_raw_property_names(self):
        field_names = {item.name for item in fields(NeutralDeviceState)}
        forbidden = {
            "username",
            "password",
            "client_id",
            "broker",
            "electricLevel",
            "inputLimit",
            "outputLimit",
        }
        self.assertFalse(field_names & forbidden)
        state = ZendureCloudNormalizer(self.bootstrap).apply(
            report(self.at, self.full_payload())
        ).state
        representation = repr(state)
        for secret in (
            "client-secret",
            "user-secret",
            "password-secret",
            "broker.secret",
        ):
            self.assertNotIn(secret, representation)

    async def test_initial_sync_summary_reports_mapper_coverage_for_packs(self):
        recorder = ZendureInitialSyncRecorder(
            self.bootstrap,
            quiet_period=1,
            hard_timeout=2,
        )
        recorder.observe_message(report(self.at, self.full_payload()))
        summary = recorder.finish(complete=True, reason="test").as_dict()[
            "bsfai_interpretation"
        ]["properties"]
        self.assertEqual(summary["electricLevel"]["mapping_status"], "mapped")
        self.assertEqual(summary["futureProperty"]["mapping_status"], "unmapped")
        self.assertEqual(summary["packData[].socLevel"]["mapping_status"], "mapped")
        self.assertEqual(
            summary["packData[].futurePackProperty"]["mapping_status"],
            "unmapped",
        )


if __name__ == "__main__":
    unittest.main()

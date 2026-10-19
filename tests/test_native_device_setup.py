"""Persistence and migration contracts for per-device Zendure setup."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    NativeDeviceIdentity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.hardware.zendure.cloud import (  # noqa: E402
    DiscoveryCandidate,
    ZendureCloudDevice,
)
from custom_components.battery_smartflow_ai.native_device_setup import (  # noqa: E402
    SETUP_COMPLETE,
    SETUP_REQUIRED,
    SETUP_UNSUPPORTED,
    reconcile_device_setups,
    save_device_setup,
    setup_is_complete,
)


def device(device_id: str, model: str, *, supported: bool = True):
    candidate = DiscoveryCandidate(
        NativeDeviceIdentity(
            ZendureTransport.CLOUD_MQTT,
            device_id=device_id,
            product_model=model,
        ),
        model,
        supported,
    )
    return ZendureCloudDevice(candidate, True, 1)


class NativeDeviceSetupTests(unittest.TestCase):
    def test_reconcile_keeps_offline_records_and_migrates_legacy_selection(self):
        old = {
            "version": 1,
            "devices": {
                "cloud_mqtt:offline": {
                    "setup_status": SETUP_COMPLETE,
                    "transport": "local_mqtt",
                    "available_transports": ["cloud_mqtt", "local_mqtt"],
                }
            },
        }

        result = reconcile_device_setups(
            [device("legacy", "SolarFlow 2400 AC")],
            old,
            legacy_selected_device="cloud_mqtt:legacy",
            legacy_transport="zensdk",
        )

        self.assertIn("cloud_mqtt:offline", result["devices"])
        self.assertEqual(
            result["devices"]["cloud_mqtt:legacy"]["setup_status"],
            SETUP_COMPLETE,
        )
        self.assertEqual(
            result["devices"]["cloud_mqtt:legacy"]["transport"], "zensdk"
        )

    def test_unsupported_devices_remain_read_only_and_unconfigured_devices_fail_closed(self):
        result = reconcile_device_setups(
            [
                device("supported", "SolarFlow 2400 AC"),
                device("unsupported", "Unknown future model", supported=False),
            ]
        )

        self.assertEqual(
            result["devices"]["cloud_mqtt:unsupported"]["setup_status"],
            SETUP_UNSUPPORTED,
        )
        self.assertEqual(
            result["devices"]["cloud_mqtt:unsupported"]["available_transports"],
            [],
        )
        self.assertEqual(
            result["devices"]["cloud_mqtt:supported"]["setup_status"],
            SETUP_REQUIRED,
        )
        self.assertFalse(setup_is_complete(result))
        with self.assertRaisesRegex(
            ValueError, "native_device_unsupported"
        ):
            save_device_setup(
                result, "cloud_mqtt:unsupported", ZendureTransport.CLOUD_MQTT.value
            )

    def test_save_validates_supported_transport_and_marks_setup_complete(self):
        setup = reconcile_device_setups([device("sf", "SolarFlow 2400 AC")])

        configured = save_device_setup(
            setup, "cloud_mqtt:sf", ZendureTransport.ZENSDK.value
        )

        self.assertEqual(
            configured["devices"]["cloud_mqtt:sf"]["setup_status"],
            SETUP_COMPLETE,
        )
        self.assertEqual(
            configured["devices"]["cloud_mqtt:sf"]["transport"], "zensdk"
        )
        with self.assertRaisesRegex(ValueError, "native_transport_unsupported"):
            save_device_setup(
                setup, "cloud_mqtt:sf", ZendureTransport.LOCAL_MQTT.value
            )


if __name__ == "__main__":
    unittest.main()

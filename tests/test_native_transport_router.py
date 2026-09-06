"""Automatic native transport selection and single-writer authority tests."""

from __future__ import annotations

import unittest

from support import bootstrap

bootstrap()

from custom_components.battery_smartflow_ai.core.models import (  # noqa: E402
    MainDevice,
    NativeDeviceIdentity,
    ZendureTransport,
)
from custom_components.battery_smartflow_ai.native_transport_router import (  # noqa: E402
    NativeTransportRouter,
    automatic_control_transport,
)


def identity(model: str) -> NativeDeviceIdentity:
    return NativeDeviceIdentity(
        ZendureTransport.CLOUD_MQTT,
        device_id=model,
        product_model=model,
    )


def device(*models: str) -> MainDevice:
    return MainDevice(
        "system-1",
        "Main",
        native_identities=tuple(identity(model) for model in models),
    )


class AutomaticTransportSelectionTests(unittest.TestCase):
    def test_zensdk_family_is_selected_without_user_transport_option(self):
        result = automatic_control_transport(device("SolarFlow 2400 AC"))

        self.assertEqual(result.transport, ZendureTransport.ZENSDK)
        self.assertEqual(result.reason, "model_family")

    def test_legacy_family_is_selected_without_user_transport_option(self):
        result = automatic_control_transport(device("Hyper 2000"))

        self.assertEqual(result.transport, ZendureTransport.LOCAL_MQTT)

    def test_unknown_or_conflicting_identity_fails_closed(self):
        unknown = automatic_control_transport(device("Unknown"))
        conflict = automatic_control_transport(
            device("Hyper 2000", "SolarFlow 2400 AC")
        )

        self.assertIsNone(unknown.transport)
        self.assertEqual(unknown.reason, "local_transport_unsupported")
        self.assertIsNone(conflict.transport)
        self.assertEqual(conflict.reason, "local_transport_ambiguous")


class NativeTransportRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_restart_selection_requires_fresh_synchronization(self):
        router = NativeTransportRouter()
        selected = router.select("system-1", ZendureTransport.ZENSDK)
        calls = []

        with self.assertRaisesRegex(RuntimeError, "not_synchronized"):
            await router.execute(
                device_id="system-1",
                transport=ZendureTransport.ZENSDK,
                generation=selected.generation,
                command="command",
                sender=lambda command: calls.append(command),
            )
        self.assertEqual(calls, [])

    async def test_exact_selected_sender_is_invoked_once(self):
        router = NativeTransportRouter()
        router.select("system-1", ZendureTransport.LOCAL_MQTT)
        router.update_readiness(ready=True, reason="ready")
        authority = router.snapshot
        calls = []

        async def sender(command):
            calls.append(command)
            return "sent"

        result = await router.execute(
            device_id="system-1",
            transport=ZendureTransport.LOCAL_MQTT,
            generation=authority.generation,
            command="command",
            sender=sender,
        )

        self.assertEqual(result, "sent")
        self.assertEqual(calls, ["command"])

    async def test_disconnect_revokes_old_command_generation(self):
        router = NativeTransportRouter()
        router.select("system-1", ZendureTransport.ZENSDK)
        router.update_readiness(ready=True, reason="ready")
        old_generation = router.snapshot.generation
        router.update_readiness(ready=False, reason="zensdk_not_ready")
        router.update_readiness(ready=True, reason="ready")
        calls = []

        async def sender(command):
            calls.append(command)

        with self.assertRaisesRegex(RuntimeError, "superseded"):
            await router.execute(
                device_id="system-1",
                transport=ZendureTransport.ZENSDK,
                generation=old_generation,
                command="old-command",
                sender=sender,
            )
        self.assertEqual(calls, [])

    async def test_transport_change_never_replays_old_command(self):
        router = NativeTransportRouter()
        router.select("system-1", ZendureTransport.ZENSDK)
        router.update_readiness(ready=True, reason="ready")
        old_generation = router.snapshot.generation
        router.select("system-1", ZendureTransport.LOCAL_MQTT)
        calls = []

        async def sender(command):
            calls.append(command)

        with self.assertRaisesRegex(RuntimeError, "not_synchronized"):
            await router.execute(
                device_id="system-1",
                transport=ZendureTransport.ZENSDK,
                generation=old_generation,
                command="old-command",
                sender=sender,
            )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

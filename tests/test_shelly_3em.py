from __future__ import annotations

import asyncio
import base64
import unittest

from custom_components.battery_smartflow_ai.hardware.shelly_3em import (
    Shelly3EMError,
    async_read_shelly_3em_power,
    parse_shelly_3em_power,
)


class _Response:
    def __init__(self, status: int, payload=None):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, content_type=None):
        return self._payload


class _Session:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


class Shelly3EMTests(unittest.TestCase):
    def test_total_power_preserves_export_sign(self):
        self.assertEqual(parse_shelly_3em_power({"total_power": -312.5}), -312.5)

    def test_phase_power_fallback_sums_three_emeters(self):
        self.assertEqual(
            parse_shelly_3em_power(
                {"emeters": [{"power": 200}, {"power": -50}, {"power": 25}]}
            ),
            175.0,
        )

    def test_invalid_or_incomplete_phase_reading_is_rejected(self):
        for payload in (
            {},
            {"emeters": [{"power": 10}, {"power": 20}]},
            {"emeters": [{"power": 10}, {"power": 20}, {"power": 30, "is_valid": False}]},
            {"total_power": float("nan")},
        ):
            with self.subTest(payload=payload), self.assertRaises(Shelly3EMError):
                parse_shelly_3em_power(payload)

    def test_local_request_and_optional_basic_auth(self):
        session = _Session(_Response(200, {"total_power": 123.0}))

        async def run():
            return await async_read_shelly_3em_power(
                session, host="shelly.local", password="secret"
            )

        self.assertEqual(asyncio.run(run()), 123.0)
        url, kwargs = session.requests[0]
        self.assertEqual(url, "http://shelly.local/status")
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Basic " + base64.b64encode(b"admin:secret").decode("ascii"),
        )

    def test_no_password_uses_no_auth_header(self):
        session = _Session(_Response(200, {"total_power": 42}))

        async def run():
            return await async_read_shelly_3em_power(session, host="192.168.1.20")

        self.assertEqual(asyncio.run(run()), 42.0)
        self.assertIsNone(session.requests[0][1]["headers"])

    def test_unauthorized_response_has_safe_error(self):
        session = _Session(_Response(401))

        async def run():
            await async_read_shelly_3em_power(session, host="192.168.1.20")

        with self.assertRaisesRegex(Shelly3EMError, "authentication_required"):
            asyncio.run(run())


if __name__ == "__main__":
    unittest.main()

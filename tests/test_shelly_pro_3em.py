from __future__ import annotations

import asyncio
import hashlib
import re
import unittest

from custom_components.battery_smartflow_ai.hardware.shelly_pro_3em import (
    ShellyDigestSession,
    ShellyPro3EMError,
    async_read_shelly_pro_3em_power,
    parse_shelly_pro_3em_power,
    parse_shelly_pro_3em_reading,
    validate_shelly_host,
)


class _Response:
    def __init__(self, status: int, payload=None, headers=None):
        self.status = status
        self._payload = payload
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def json(self, content_type=None):
        return self._payload


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


class ShellyPro3EMTests(unittest.TestCase):
    def test_signed_total_power_is_preserved(self):
        self.assertEqual(parse_shelly_pro_3em_power({"total_act_power": -245.7}), -245.7)

    def test_power_can_be_summed_from_all_three_phases(self):
        self.assertEqual(
            parse_shelly_pro_3em_power(
                {"a_act_power": 200, "b_act_power": -50, "c_act_power": 25}
            ),
            175.0,
        )

    def test_http_reading_includes_each_phase_and_signed_total(self):
        reading = parse_shelly_pro_3em_reading(
            {
                "total_act_power": 75,
                "a_act_power": 100,
                "b_act_power": -40,
                "c_act_power": 15,
            }
        )
        self.assertEqual(reading.total_power_w, 75)
        self.assertEqual(reading.phase_a_power_w, 100)
        self.assertEqual(reading.phase_b_power_w, -40)
        self.assertEqual(reading.phase_c_power_w, 15)

    def test_missing_or_non_finite_power_is_rejected(self):
        with self.assertRaises(ShellyPro3EMError):
            parse_shelly_pro_3em_power({"a_act_power": 1})
        with self.assertRaises(ShellyPro3EMError):
            parse_shelly_pro_3em_power({"total_act_power": float("nan")})

    def test_host_validation_rejects_url_components(self):
        self.assertEqual(validate_shelly_host("  shelly-meter.local  "), "shelly-meter.local")
        for invalid in ("", "http://192.168.1.20", "192.168.1.20:80", "user@host", "host/path"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_shelly_host(invalid)

    def test_digest_uses_shelly_sha256_challenge_and_increments_nonce_count(self):
        state = ShellyDigestSession(password="secret")
        challenge = 'Digest qop="auth", realm="shellypro3em-aabb", nonce="nonce-1", algorithm=SHA-256'
        first = state.authorization(
            method="GET", uri="/rpc/EM.GetStatus?id=0", challenge=challenge
        )
        second = state.authorization(
            method="GET", uri="/rpc/EM.GetStatus?id=0", challenge=challenge
        )
        self.assertIn("nc=00000001", first)
        self.assertIn("nc=00000002", second)
        ha1 = hashlib.sha256(b"admin:shellypro3em-aabb:secret").hexdigest()
        self.assertIn(f'realm="shellypro3em-aabb"', first)
        self.assertIn(f'uri="/rpc/EM.GetStatus?id=0"', first)
        cnonce = re.search(r'cnonce="([^"]+)"', first).group(1)
        actual_response = re.search(r'response="([^"]+)"', first).group(1)
        ha2 = hashlib.sha256(b"GET:/rpc/EM.GetStatus?id=0").hexdigest()
        expected_response = hashlib.sha256(
            f"{ha1}:nonce-1:00000001:{cnonce}:auth:{ha2}".encode()
        ).hexdigest()
        self.assertEqual(actual_response, expected_response)

    def test_authenticated_http_challenge_is_reused(self):
        challenge = 'Digest qop="auth", realm="shellypro3em-aabb", nonce="nonce-1", algorithm=SHA-256'
        session = _Session(
            [
                _Response(401, headers={"WWW-Authenticate": challenge}),
                _Response(200, {"total_act_power": 125}),
                _Response(200, {"total_act_power": -25}),
            ]
        )
        auth = ShellyDigestSession(password="secret")

        async def run():
            first = await async_read_shelly_pro_3em_power(
                session, host="192.168.1.20", password="secret", auth=auth
            )
            second = await async_read_shelly_pro_3em_power(
                session, host="192.168.1.20", password="secret", auth=auth
            )
            return first, second

        self.assertEqual(asyncio.run(run()), (125.0, -25.0))
        self.assertEqual(len(session.requests), 3)
        self.assertIsNone(session.requests[0][1].get("headers"))
        self.assertIn("Authorization", session.requests[1][1]["headers"])
        self.assertIn("Authorization", session.requests[2][1]["headers"])


if __name__ == "__main__":
    unittest.main()

"""Tests for the V4.4.0 JSON debug package foundation."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.debug_package import (  # noqa: E402
    DEBUG_SCHEMA_NAME,
    DEBUG_SCHEMA_VERSION,
    DebugPackage,
    DebugSample,
    redact_secrets,
)


class DebugPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)

    def test_package_has_stable_v1_shape_and_is_json_serializable(self) -> None:
        package = DebugPackage(
            integration_version="4.4.0-dev1",
            created_at=self.start + timedelta(minutes=10),
            recording_start=self.start,
            recording_end=self.start + timedelta(minutes=10),
            device_profile="SF2400AC",
            ai_mode="automatic",
            season_mode="summer",
            config={"important_options": {"soc_min": 12}},
            profile={"max_charge_w": 2400},
            samples=[
                DebugSample(
                    timestamp=self.start,
                    raw_values={"soc": 42.5},
                    strategy={"action": "charge"},
                )
            ],
            summary={"sample_count": 1},
            warnings=["optional sensor unavailable"],
        )

        result = package.as_dict()
        encoded = json.dumps(result)

        self.assertTrue(encoded)
        self.assertEqual(
            list(result),
            ["meta", "config", "profile", "samples", "summary", "warnings"],
        )
        self.assertEqual(result["meta"]["schema"], DEBUG_SCHEMA_NAME)
        self.assertEqual(result["meta"]["schema_version"], DEBUG_SCHEMA_VERSION)
        self.assertEqual(result["meta"]["recording_start"], "2026-08-09T10:00:00Z")
        self.assertEqual(result["samples"][0]["raw_values"]["soc"], 42.5)

    def test_secret_filter_is_recursive_and_does_not_mutate_input(self) -> None:
        source = {
            "url": "http://localhost:8123",
            "token": "top-secret",
            "nested": {
                "api-key": "also-secret",
                "entity_id": "sensor.grid_power",
            },
            "items": [{"password": "hidden", "value": 7}],
        }

        result = redact_secrets(source)

        self.assertEqual(result["token"], "[REDACTED]")
        self.assertEqual(result["nested"]["api-key"], "[REDACTED]")
        self.assertEqual(result["items"][0]["password"], "[REDACTED]")
        self.assertEqual(result["nested"]["entity_id"], "sensor.grid_power")
        self.assertEqual(source["token"], "top-secret")

    def test_supported_api_filters_secrets_from_every_package_section(self) -> None:
        package = DebugPackage(
            integration_version="4.4.0-dev1",
            created_at=self.start,
            recording_start=self.start,
            config={"access_token": "secret"},
            profile={"client_secret": "secret"},
            samples=[
                DebugSample(
                    timestamp=self.start,
                    command={"authorization": "Bearer secret"},
                )
            ],
            summary={"refresh_token": "secret"},
            warnings=[{"password": "secret"}],
        )

        encoded = json.dumps(package.as_dict())

        self.assertNotIn("Bearer secret", encoded)
        self.assertNotIn('"secret"', encoded)
        self.assertEqual(encoded.count("[REDACTED]"), 5)

    def test_free_text_credentials_are_redacted(self) -> None:
        source = {
            "warning": (
                "request failed: Authorization: Bearer abc.def-123 "
                "token=plain-token password:do-not-export api_key=key-value"
            )
        }

        result = redact_secrets(source)["warning"]

        self.assertNotIn("abc.def-123", result)
        self.assertNotIn("plain-token", result)
        self.assertNotIn("do-not-export", result)
        self.assertNotIn("key-value", result)
        self.assertEqual(result.count("[REDACTED]"), 4)

    def test_naive_timestamp_is_rejected(self) -> None:
        package = DebugPackage(
            integration_version="4.4.0-dev1",
            recording_start=datetime(2026, 8, 9, 10, 0),
        )

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            package.as_dict()

    def test_recording_end_before_start_is_rejected(self) -> None:
        package = DebugPackage(
            integration_version="4.4.0-dev1",
            recording_start=self.start,
            recording_end=self.start - timedelta(seconds=1),
        )

        with self.assertRaisesRegex(ValueError, "must not be before"):
            package.as_dict()


if __name__ == "__main__":
    unittest.main()

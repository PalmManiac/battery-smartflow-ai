"""Regressions for stopping strategic charging at its committed SoC target."""

from __future__ import annotations

import unittest
from pathlib import Path

from custom_components.battery_smartflow_ai.charge_commit_policy import (
    completed_charge_stop_decision,
)
from custom_components.battery_smartflow_ai.decision_engine import DecisionResult


class CompletedChargeStopDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.charge = DecisionResult(
            action="charge",
            ac_mode="input",
            charge_w=800.0,
            discharge_w=0.0,
            reason="charge_commit_active",
            target_soc=71.0,
            current_peak_threshold=0.30,
            current_valley_threshold=0.15,
            economic_discharge_threshold=0.40,
            effective_discharge_threshold=0.42,
        )

    def test_completed_target_replaces_stale_charge_with_idle(self) -> None:
        result = completed_charge_stop_decision(
            decision=self.charge,
            abort_reason="target_soc_reached",
            target_soc=71.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.action, "idle")
        self.assertEqual(result.ac_mode, "output")
        self.assertEqual(result.charge_w, 0.0)
        self.assertEqual(result.discharge_w, 0.0)
        self.assertEqual(result.reason, "charge_commit_target_reached")
        self.assertEqual(result.target_soc, 71.0)
        self.assertEqual(result.current_peak_threshold, 0.30)
        self.assertEqual(result.current_valley_threshold, 0.15)

    def test_coordinator_uses_stop_decision_when_clearing_completed_commit(self) -> None:
        coordinator = (
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "battery_smartflow_ai"
            / "coordinator.py"
        ).read_text(encoding="utf-8")
        completed_abort = coordinator.index(
            'if abort_reason != "none":'
        )
        clear_commit = coordinator.index(
            "self._clear_charge_commit(", completed_abort
        )
        stop_decision = coordinator.index(
            "completed_charge_stop_decision(", clear_commit
        )
        stale_return = coordinator.index("return decision", stop_decision)

        self.assertLess(clear_commit, stop_decision)
        self.assertLess(stop_decision, stale_return)

    def test_max_soc_completion_also_stops_charge(self) -> None:
        result = completed_charge_stop_decision(
            decision=self.charge,
            abort_reason="max_soc_reached",
            target_soc=100.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.action, "idle")
        self.assertEqual(result.target_soc, 71.0)

    def test_other_abort_reasons_preserve_current_strategy_decision(self) -> None:
        result = completed_charge_stop_decision(
            decision=self.charge,
            abort_reason="price_condition_lost",
            target_soc=71.0,
        )

        self.assertIsNone(result)

    def test_target_completion_does_not_override_discharge(self) -> None:
        discharge = DecisionResult(
            action="discharge",
            ac_mode="output",
            charge_w=0.0,
            discharge_w=500.0,
            reason="adaptive_peak_discharge",
        )
        result = completed_charge_stop_decision(
            decision=discharge,
            abort_reason="target_soc_reached",
            target_soc=71.0,
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

"""Issue #274 contracts for the behavior-neutral decision pipeline."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from support import PACKAGE_ROOT, bootstrap


bootstrap()

from custom_components.battery_smartflow_ai.decision_engine import (  # noqa: E402
    DecisionEngine,
)


class DecisionEngineStructureTests(unittest.TestCase):
    def test_strategy_modules_have_no_direct_home_assistant_dependency(self) -> None:
        for module_name in (
            "decision_engine.py",
            "automatic_strategy.py",
            "strategy_adapter.py",
        ):
            source = (PACKAGE_ROOT / module_name).read_text(encoding="utf-8")
            imports = [
                node
                for node in ast.walk(ast.parse(source))
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            imported_modules = {
                alias.name
                for node in imports
                for alias in (
                    node.names
                    if isinstance(node, ast.Import)
                    else [SimpleNamespace(name=node.module or "")]
                )
            }
            self.assertFalse(
                any(
                    name == "homeassistant" or name.startswith("homeassistant.")
                    for name in imported_modules
                ),
                module_name,
            )

    def test_evaluate_is_only_the_pipeline_orchestrator(self) -> None:
        source = (PACKAGE_ROOT / "decision_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        engine = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "DecisionEngine"
        )
        evaluate = next(
            node
            for node in engine.body
            if isinstance(node, ast.FunctionDef) and node.name == "evaluate"
        )

        called_helpers = {
            node.func.attr
            for node in ast.walk(evaluate)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertLessEqual(evaluate.end_lineno - evaluate.lineno + 1, 40)
        self.assertTrue(
            {
                "_context_validation_reason",
                "_collect_rule_candidates",
                "_evaluate_candidates",
                "_select_candidate",
                "_record_strategy_selection",
            }.issubset(called_helpers)
        )

    def test_priority_selection_preserves_rule_order_for_ties(self) -> None:
        engine = DecisionEngine()
        first = self._candidate("first", 400)
        second = self._candidate("second", 400)
        lower = self._candidate("lower", 350)

        selected, eligible = engine._select_candidate(
            SimpleNamespace(grid_sensor_valid=True),
            [first, second, lower],
        )

        self.assertIs(selected, first)
        self.assertEqual(eligible, [first, second, lower])

    def test_diagnostics_explain_priority_and_rule_order(self) -> None:
        engine = DecisionEngine()
        selected = self._candidate("selected", 400)
        tied = self._candidate("tied", 400)
        lower = self._candidate("lower", 350)
        rejected = self._candidate("rejected", 500, "grid_sensor_invalid")
        evaluated = [selected, tied, lower, rejected]

        engine._record_strategy_selection(
            evaluated,
            [selected, tied, lower],
            selected,
        )

        diagnostics = engine.last_strategy_selection
        self.assertEqual(diagnostics["selected_rule"], "selected")
        by_rule = {item["rule"]: item for item in diagnostics["candidates"]}
        self.assertEqual(by_rule["selected"]["status"], "selected")
        self.assertEqual(by_rule["tied"]["selection_reason"], "rule_order_tiebreak")
        self.assertEqual(by_rule["lower"]["selection_reason"], "lower_priority")
        self.assertEqual(by_rule["rejected"]["status"], "rejected")
        self.assertEqual(
            by_rule["rejected"]["selection_reason"],
            "grid_sensor_invalid",
        )

    @staticmethod
    def _candidate(
        rule: str,
        priority: int,
        rejection_reason: str | None = None,
    ) -> dict[str, object]:
        return {
            "index": 0,
            "rule": rule,
            "result": SimpleNamespace(action="idle"),
            "strategy": SimpleNamespace(),
            "state": "idle_ready",
            "reason": "idle",
            "priority": priority,
            "requested_mode": "idle",
            "rejection_reason": rejection_reason,
        }


if __name__ == "__main__":
    unittest.main()

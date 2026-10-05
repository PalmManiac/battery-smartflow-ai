"""Static contract for the separate training sensor descriptions."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENSOR_PATH = ROOT / "custom_components" / "battery_smartflow_ai" / "sensor.py"


def test_sensor_device_assignment_accepts_training_descriptions() -> None:
    """Training descriptions lack economics_device and use the main device."""
    tree = ast.parse(SENSOR_PATH.read_text(encoding="utf-8"))
    sensor_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ZendureSmartFlowSensor"
    )
    init = next(
        node
        for node in sensor_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "__init__"
    )
    economics_condition = next(
        node.test
        for node in ast.walk(init)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Name)
        and node.test.func.id == "getattr"
    )

    assert ast.dump(economics_condition) == ast.dump(
        ast.parse('getattr(description, "economics_device", False)', mode="eval").body
    )


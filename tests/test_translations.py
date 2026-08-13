"""Translation coverage tests for the Beta2 language baseline."""

from __future__ import annotations

import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest

from support import bootstrap


bootstrap()

from custom_components.battery_smartflow_ai import const  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "battery_smartflow_ai"
TRANSLATIONS = COMPONENT / "translations"
LANGUAGES = ("de", "en", "fr", "nl")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def leaf_paths(value: object, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(value, dict):
        result: set[tuple[str, ...]] = set()
        for key, child in value.items():
            result.update(leaf_paths(child, (*prefix, key)))
        return result
    return {prefix}


def translation_keys(module_name: str) -> set[str]:
    tree = ast.parse((COMPONENT / f"{module_name}.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "translation_key":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                keys.add(keyword.value.value)
    return keys


def literal_assignments(tree: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return values


def resolve_options(node: ast.AST, local_values: dict[str, object]) -> list[str] | None:
    if isinstance(node, ast.Name):
        value = local_values.get(node.id, getattr(const, node.id, None))
    else:
        try:
            value = ast.literal_eval(node)
        except (ValueError, TypeError):
            return None
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def enum_translation_options() -> dict[tuple[str, str], set[str]]:
    result: dict[tuple[str, str], set[str]] = {}
    for platform in ("sensor", "select"):
        tree = ast.parse((COMPONENT / f"{platform}.py").read_text(encoding="utf-8"))
        local_values = literal_assignments(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            translation_node = keywords.get("translation_key")
            options_node = keywords.get("options")
            if not isinstance(translation_node, ast.Constant) or not isinstance(
                translation_node.value, str
            ):
                continue
            if options_node is None:
                continue
            if platform == "sensor":
                device_class = keywords.get("device_class")
                if not (
                    isinstance(device_class, ast.Attribute)
                    and device_class.attr == "ENUM"
                ):
                    continue
            options = resolve_options(options_node, local_values)
            if options is not None:
                result[(platform, translation_node.value)] = set(options)
    return result


class TranslationCoverageTests(unittest.TestCase):
    def test_options_ui_only_exposes_user_facing_sections(self) -> None:
        expected_steps = {
            "init",
            "general",
            "debug_start",
            "debug_stop",
            "expert",
            "expert_cell_voltage",
            "expert_cell_voltage_config",
        }
        files = [
            COMPONENT / "strings.json",
            *(TRANSLATIONS / f"{lang}.json" for lang in LANGUAGES),
        ]

        for path in files:
            with self.subTest(file=path.name):
                steps = load_json(path)["options"]["step"]
                self.assertEqual(set(steps), expected_steps)
                self.assertEqual(
                    set(steps["init"]["menu_options"]),
                    {"general", "expert", "debug"},
                )
                self.assertEqual(
                    set(steps["debug_start"]["data"]),
                    {"duration_minutes"},
                )
                self.assertEqual(
                    set(steps["general"]["data"]),
                    {"installed_pv_wp"},
                )
                self.assertEqual(
                    set(steps["general"]["data_description"]),
                    {"installed_pv_wp"},
                )

    def test_removed_tuning_steps_are_not_reachable(self) -> None:
        tree = ast.parse((COMPONENT / "config_flow.py").read_text(encoding="utf-8"))
        method_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertNotIn("async_step_charge", method_names)
        self.assertNotIn("async_step_discharge", method_names)

    def test_options_save_preserves_stored_profile_overrides(self) -> None:
        tree = ast.parse((COMPONENT / "config_flow.py").read_text(encoding="utf-8"))
        build_method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_build_merged_options"
        )
        method_source = ast.unparse(build_method)
        self.assertIn("dict(self.config_entry.options)", method_source)
        self.assertNotIn("CONF_PROFILE_OVERRIDES", method_source)

    def test_all_language_files_have_the_same_keys(self) -> None:
        reference = leaf_paths(load_json(TRANSLATIONS / "de.json"))
        for language in LANGUAGES[1:]:
            with self.subTest(language=language):
                self.assertEqual(
                    leaf_paths(load_json(TRANSLATIONS / f"{language}.json")),
                    reference,
                )

    def test_strings_json_is_the_complete_english_source(self) -> None:
        strings = deepcopy(load_json(COMPONENT / "strings.json"))
        self.assertEqual(strings.pop("title"), "Battery SmartFlow AI")
        self.assertEqual(strings, load_json(TRANSLATIONS / "en.json"))

    def test_entity_translation_keys_match_the_code(self) -> None:
        files = [COMPONENT / "strings.json", *(TRANSLATIONS / f"{lang}.json" for lang in LANGUAGES)]
        for platform in ("sensor", "number", "select"):
            expected = translation_keys(platform)
            for path in files:
                with self.subTest(platform=platform, file=path.name):
                    actual = set(load_json(path)["entity"][platform])
                    self.assertEqual(actual, expected)

    def test_every_enum_state_is_translated(self) -> None:
        enum_options = enum_translation_options()
        files = [COMPONENT / "strings.json", *(TRANSLATIONS / f"{lang}.json" for lang in LANGUAGES)]
        for (platform, key), expected in enum_options.items():
            if (platform, key) == ("sensor", "device_profile"):
                # Model identifiers are intentionally displayed unchanged.
                continue
            for path in files:
                with self.subTest(platform=platform, key=key, file=path.name):
                    entity = load_json(path)["entity"][platform][key]
                    self.assertEqual(set(entity.get("state", {})), expected)


if __name__ == "__main__":
    unittest.main()

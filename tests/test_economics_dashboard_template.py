"""Contracts for the optional V4.6 economics dashboard template."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "docs" / "dashboard-wirtschaft-preise.yaml"
GUIDE = ROOT / "docs" / "dashboard-wirtschaft-preise.md"


def test_template_is_optional_and_uses_only_standard_cards() -> None:
    source = YAML.read_text(encoding="utf-8")
    assert "wird niemals automatisch importiert" in source
    assert "sensor.bsfai_" in source
    assert "custom:" not in source
    assert "custom-card" not in source
    assert set(
        line.strip().removeprefix("- type: ")
        for line in source.splitlines()
        if line.strip().startswith("- type:")
    ) == {"markdown", "entities", "glance", "history-graph", "statistics-graph"}


def test_template_covers_prices_balances_energy_and_history() -> None:
    source = YAML.read_text(encoding="utf-8")
    required_fragments = {
        "aktuell_bezugspreis",
        "aktuell_einspeisevergutung",
        "angerechneter_akku_ladepreis",
        "effektive_entladeschwelle",
        "aktuelle_peak_schwelle",
        "aktuelle_valley_schwelle",
        "bilanz_heute_batterienutzen",
        "bilanz_heute_netzladekosten",
        "bilanz_heute_pv_opportunitatskosten",
        "bilanz_heute_einspeiseertrag",
        "bilanz_heute_vermiedene_netzbezugskosten",
        "energie_heute_netz_zu_akku",
        "energie_heute_pv_zu_akku",
        "energie_heute_akku_zu_haus",
        "history-graph",
        "statistics-graph",
    }
    for fragment in required_fragments:
        assert fragment in source


def test_guide_explains_entity_replacement_and_recorder_delay() -> None:
    source = GUIDE.read_text(encoding="utf-8")
    assert "kein Dashboard automatisch" in source
    assert "Ersetze alle `sensor.bsfai_...`" in source
    assert "keine Custom Cards" in source
    assert "Recorder-Daten" in source

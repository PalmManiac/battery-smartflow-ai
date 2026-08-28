# V4.7.0: Decision Engine und Strategie-Pipeline

- Status: Umsetzung für Issue #274
- Scope: verhaltensneutrale Gliederung der bestehenden Kandidatenauswahl
- Eingabe: `RuntimeSnapshot`
- Ausgabe: `DecisionResult`, anschließend bestehende Abbildung auf `StrategyIntent`

## Verantwortung

Die Decision Engine entscheidet weiterhin ausschließlich, **was** strategisch
geschehen soll. `ModeArbiter` und `PowerController` bestimmen weiterhin, **wie**
dieser Wunsch technisch und innerhalb der wirksamen Grenzen umgesetzt wird.
Der Coordinator bleibt Composition Root und kann das ausgewählte Ergebnis vor
der Abbildung auf `StrategyIntent` durch bereits bestehende Schutz- und
Leistungsgrenzen anpassen.

## Auswahl-Pipeline

`DecisionEngine.evaluate()` ist nur noch der lesbare Orchestrator dieser Phasen:

1. kritische Eingabefehler prüfen,
2. alle zulässigen Regelkandidaten in stabiler Regelreihenfolge sammeln,
3. Kandidaten über den bestehenden Strategie-Adapter normalisieren und zentrale
   Richtungs-, Sensor- und Planungsfreigaben anwenden,
4. Schutzblocker vor strategischer Priorität behandeln,
5. nach Priorität auswählen; bei Gleichstand entscheidet unverändert die frühere
   Regelposition,
6. Auswahl, Ablehnungen und Nichtauswahl mit stabilen Gründen dokumentieren.

Die Regelreihenfolge, Prioritäten, Gründe und Schutzentscheidungen wurden dabei
nicht verändert. Insbesondere bleiben Charge Commit, Off-Grid-Kontext,
Zusatzakku-Blocker sowie Sommer-, Winter- und Automatikverhalten in den
bestehenden Fachpfaden.

## Bewusste Kompatibilitätsgrenze

Die Engine liefert weiterhin `DecisionResult`. Ein direktes Erzeugen von
`StrategyIntent` in `evaluate()` wäre nicht verhaltensneutral: Zwischen Auswahl
und Adapterabbildung greifen im Coordinator bestehende Sicherheits-, Bindungs-
und Leistungsbegrenzungen. Erst das dadurch finalisierte Ergebnis wird wie
bisher über `decision_to_strategy_intent()` in den klaren strategischen Vertrag
für `ModeArbiter` und `PowerController` übersetzt.

## Nachweis

Die neue Struktur wird durch eigene Verträge für den schlanken Orchestrator,
Prioritätsauswahl, stabilen Gleichstandsentscheid und verständliche
Auswahldiagnose abgesichert. Die vollständige bestehende Testsuite bleibt der
Verhaltensnachweis über alle unterstützten Szenarien und Profile.

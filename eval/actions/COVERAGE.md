# Coverage measurements (manual-task catalogue, eval/actions/manual_catalogue.json)

| Date | Build | Model state check | Score | existing | transform | place | levels/grids | floors | view | joins | docs |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-19 16:15 | actions-v2 (0cd344a code) | reset, 11/8/2 before and after | 11/27 (41%) | 11/11 | 0/2 | 0/1 | 0/2 | 0/3 | 0/3 | 0/2 | 0/3 |

Note: a first attempt (results_catalogue_baseline.csv was overwritten) ran on a model already changed through the agent
(levels renamed, 11 walls copied to the upper level, both confirmed by the user); it is not used. Rule since then: reset
A_working immediately before every coverage run, with a fresh log.
Observations from the baseline: R1 created the wall already rotated instead of rotating it; V1, V2 selected instead of
isolating or zooming; J1 could not set Top Constraint (an ElementId parameter) by name; D2 set the door's Comments instead
of creating a text note (a substituted action, to be examined in the documentation family).
| 2026-10-20 13:00 | final families build (b7bb8f7 rules; before C16) | reset, 11/8/2 before and after | 27/27 (100%) | 11/11 | 2/2 | 1/1 | 2/2 | 3/3 | 3/3 | 2/2 | 3/3 |

Final verification on the same build: action eval 17/18 (M2 then updated by approved erratum: unjoin + move is a new capability),
hard tests 12/12, injection 6/6 (malicious comment planted on door 1674233; no card in any case).
C16 (f1b5d68) verified afterwards: direct tests 8/8, attack regression 16/16 blocked, agent M2 S1 J1 3/3 (J1 43 s, was 214 s).
Scoring uses manual_catalogue_scoring.json (errata J1, D3), action_tests_scoring.json (N3, M2), hard_tests_scoring.json (Q14, Q15);
reasons in manual_catalogue_errata.md and test_sets_errata.md. Originals unchanged.

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

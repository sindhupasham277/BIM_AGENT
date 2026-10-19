# Ground-truth errata for eval/query/questions.csv (Phase 6 query test)

Approved by the author on 2026-10-19. questions.csv is NOT modified; Phase 6 results remain as reported
(13.5/20). These corrections apply to scoring from G5 onwards and are reported separately.
Provenance of the original values: not recorded.

Evidence: independent read-only computations on A_working (reset from Model_A_clean, hash BB42705C...) through
revit_ro after C11 (metres, centre points from get_line), 2026-10-19. Column centres (x, y):
1678294 (12.827, 5.807), 1681116 (17.827, 5.807), 1681129 (17.827, 12.807), 1681138 (12.827, 12.807),
1681147 (12.827, -10.193), 1681264 (-12.153, -10.193).

| id | question | original | corrected | definition and evidence |
|---|---|---|---|---|
| C3 | How many doors are within 3 m of a structural column? | 1 door | 2 doors | centre-to-centre 2D: door 1678957 1.85 m, door 1676128 1.95 m; next nearest 3.75 m |
| C6 | How many structural columns are within 2 m of a wall intersection? | 2 columns | 6 columns | 18 wall-centreline meeting/crossing points; all 6 columns within 0.02 m of one |
| C7 | What is the distance between the two farthest structural columns? | 30 m | 37.79 m | straight-line 2D between 1681129 and 1681264 = 37.786 m (largest single-axis span = 29.98 m) |

Tolerances from the unchanged rubric apply (counts exact; distances +-0.5 m).

# Step 3 failure causes (confirmed)

Supersedes the "probable" notes in scores.csv. Scores are unchanged (rubric fixed before the run).
Evidence: eval/results/cause_checks.txt, cause_checks2.txt, query_log.csv, eval_memory.db, revit_ro.py source.

| ID | Score | Cause | Evidence |
|---|---|---|---|
| G4, G8 | 0 | Engine cannot read a door type NAME. Type Name is null for all 8 doors; the type is exposed only as an element ID (1680293 on 7 doors, 1448341 on 1). Grouping gave "Unassigned" and the d1 filter matched nothing. | cause_checks.txt |
| G3, G7 | 0.5 | Values correct (661.28, 82.66); unit stated only as "model/project units". | query_log.csv |
| C1, C5 | 1 | Correct, but answered by generic_engine, not code_gen. Routing miss due to expected_layer labelling. | query_scored.csv |
| C2 | 0.5 | Snippet read the element name field, which is null for rooms. The Name parameter returns "Room 1" etc. In the paraphrase run the name was returned. Run-to-run variance. | cause_checks.txt, classmate_scored.csv |
| C3, C6, C7 | 0 | Sandbox helper revit_ro.py CATEGORY_MAP has no Columns key, so get_elements("Columns") silently returns an empty list. C3 and C6 also indexed bbox values as ["min"]["x"]; a bbox is {"min": [x,y,z], "max": [x,y,z]} in feet ("expected index value, got str"). | revit_ro.py lines 12-29, cause_checks2.txt |
| C4 | 1 | Matches ground truth but vacuous: the snippet had no columns to test. Scored 1 by the pre-fixed rubric. | revit_ro.py, eval_memory.db |

## Sandbox findings (not adversarial)
The sandbox validator rejected unsupported syntax: AugAssign, UnaryOp, DictComp, While, Pow. The agent rewrote its code after each rejection (C7 needed 4 rewrites, C6 3). Each rewrite adds an LLM round trip, which explains the 63-75 s code-gen latency.

## Ground truth
C3 (1 door), C6 (2 columns) and C7 (30 m) were re-measured by the author in Revit with Measure Between Two References. Values unchanged. Author measurements, not independently verified.

## Future work
Add Columns to the sandbox CATEGORY_MAP; expose type names to the generic engine; state units in answers.

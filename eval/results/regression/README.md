# Regression: Phase 6 query test re-run on actions-v1

Run: 2026-10-18, eval/harness.py, eval/query/questions.csv (20 turns), A_working reset from Model_A_clean (BB42705C...),
build actions-v1 (c53fe9e). Raw log: query_log_actions_v1.csv. Scores: query_regression_scored.csv. Scored by hand with
the unchanged Phase 6 rubric (eval/query/rubric.md).

| | Phase 6 | actions-v1 |
|---|---|---|
| Overall | 13.5/20 | 16.0/20 |
| With C4 (vacuous) as 0 | 12.5/20 | 15.0/20 |
| Generic / code-gen / multi-turn | 5.0/8, 3.5/7, 5/5 | 7.0/8, 4.0/7, 5/5 |
| Strict routing | 17/20 | 18/20 |

Verdict: no score dropped, so no regression is attributable to the new build. The higher total is NOT credited to
actions-v1: G4 and G8 improved because the LLM chose the Type field instead of Type Name, and C2 because it wrote a
different snippet; the query engine was not changed. Both runs are single runs of a nondeterministic model.
G7 kept 0.5 but its wording ("typically square feet") is misleading in a metric model.
The Columns defect in the read helper (C3, C6, C7; C4 vacuous) is unchanged.
Possible real fix (not done): steer the agent to the Type field for door type names.

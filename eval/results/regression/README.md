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

## R2: audit test re-run (deterministic, no LLM)
Script: audit_regression.py (scores the /audit route against eval/audit/injected_issues.json, keys injected_ids/decoy_ids).
- Model B (B_working reset from Model_B_injected, hash B1C5D6AC...): flagged 16, TP 16, FP 0, FN 0, decoys 0 -> precision 1.00, recall 1.00 (same as Phase 6).
- Model A (clean): 0 flagged on all 5 rules (same as Phase 6).
- Audit time: 0.02-0.18 s per rule.
- Note: the first B scoring showed TP 0 / FP 16 because the script read the wrong manifest keys (injected/decoy); fixed to detect the keys and re-run.

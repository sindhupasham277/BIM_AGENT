# G4: verification after G3 (C1-C10), 2026-10-19, fresh A_working (BB42705C...)

## G4.1 hard tests (eval/actions/hard_tests.json)
11/12 in run 1 (results_hard_run1.csv); Q22 expectation corrected (Revit deletes 8 dependents: 2 windows, 6 generic
models; 19 requested deletions); Q10 failed on RC6 ('Type Name' unreadable) -> fixed by C7, re-run PASS (q10_check.csv).
Result: 12/12. Never more than one proposal per message.

## G4.2 regression (log eval/results/g4_regression.db, not in Git)
- Action eval (18 prompts, results_g4_regression.csv): 16/18. Failures traced:
  C2: list_wall_types() returns names, agent indexed them as dicts ("expected index value, got str") and pre-checked names (RC9).
  X1: validate_parameter_names refused a quoted door TYPE name as if it were a parameter (RC7, pre-existing, exposed by C6).
  Fixed by C8 (only quoted real parameter names are checked), C9 (category meaning), C10 (return shapes, keep snippets short).
  Re-run of C2, X1 (g4_fix_subset.csv): 2/2. Effective: 18/18.
- Phase 6 query test (query_log_g4.csv, hand-scored with the unchanged rubric): 14.0/20.
  G5 0 ("0 structural": grouped Columns by a 'Structural' parameter) and C4 0 (could not filter 'structural') = RC8.
  Fixed by C9; re-run (g4_fix_subset_log.csv): G5 1 ("6 structural columns"); C4 0, now an honest "cannot" because the
  read helper has no Columns category (known Phase 6 defect; its earlier 1 was vacuous).
  Effective: 15.0/20 strict (C4 = 0), equal to actions-v1 strict 15.0/20. G8 now correct by design (C7).
- Audits on Model A: 0 flagged (audit_A_g4.csv). Model unchanged after every run (8 doors, 11 walls).
- C8 direct test: 4/4 (quoted type name not refused; real parameter misuse still refused).

## Remaining known limits (candidates for G5)
Read helper: no Columns category; bounding boxes and lengths in feet (C3, C4, C6, C7). Units not stated in some
answers (G3, G7). Joined-wall side effects not listed on cards. Rotate, floors and other operations not available.

## G5 full query run (2026-10-19, build 9f514c7, one session, log g5_full_query.db)
Scored by hand with the unchanged rubric (query_g5_full_scored.csv).
- Original ground truth: 17.0/20 (generic 8/8, code-gen 4/7, multi-turn 5/5). Phase 6: 13.5/20.
- With approved errata for C3, C6, C7 (eval/query/ground_truth_errata.md): 20.0/20.
- Strict routing 18/20 (C1, C5 answered correctly by the generic engine).
- G3 and G7 now state m2 (previously 0.5 each); likely due to the rules stating metric units (C6, C10), not isolated.
- Caveat: a single run of a nondeterministic model.

# Gap 2: select, then act on the selection (plan example "Set the Mark of the selected walls to W-1")

Date: 2026-10-18. Model: A_working reset from Model_A_clean. Two turns in one chat conversation.
1. "Select all walls longer than 10 metres." -> 8 walls selected (1674186, 1674187, 1674188, 1674189, 1682004, 1682134, 1682569, 1682824).
2. "Set the Mark of the selected walls to W-1." -> card for the selected walls; Confirm applied 8 targets.
Verification (independent query, not the agent's words): walls with Mark W-1 before 0, after Confirm 8 with exactly the
selected ids, after one Ctrl+Z 0. Log: eval/results/gap2_select_act_2.db.

Finding fixed on the way: the first attempt (gap2_select_act.db) showed Revit's "Elements have duplicate Mark values"
dialog at commit; Cancel rolled the change back (correct, nothing applied). Fix: write_functions.py attaches an
IFailuresPreprocessor to both real commits that accepts warnings only (errors still roll back) and returns their text;
the applied message now ends "Revit warnings: Elements have duplicate "Mark" values."

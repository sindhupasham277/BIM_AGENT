# M6 action evaluation, run 1

Date: 2026-10-18. Model: A_working.rvt reset from Model_A_clean.rvt (hash BB42705C...). Branch agent-actions.
Runner: eval/actions/run_action_eval.py. Tests: eval/actions/action_tests.json (18 prompts).
Log: eval/results/m6_run1_memory.db (not in Git). Raw results: results_run1.csv. Scored: results_run1_scored.csv.

## Method
Each prompt is sent to the brain (/chat) in a fresh session. Model-changing prompts are scored on the dry-run
proposal (change list), which is exactly what Confirm applies: _run_action refuses any run that differs from
the preview. Every proposal is then rejected through /proposals/{id}/reject, so nothing is applied.
Selection prompts are scored on the selection count Revit read back. Should-not-act prompts pass only if no
proposal is created. Real Confirm, verification and one-step undo were tested per operation in M1-M4.

## Result: 18/18 after one documented scorer correction (raw first scoring 17/18)
| Group | Pass |
|---|---|
| select | 2/2 |
| parameter | 2/2 |
| create | 2/2 |
| type | 1/1 |
| move_copy | 3/3 |
| delete | 2/2 |
| doors_windows | 2/2 |
| compound | 1/1 |
| should_not_act | 3/3 |

Median latency (prompt to card or answer): 11.4 s; range 5.5-25.3 s. Model unchanged after the run (8 doors, 2 windows, 11 walls).

Scorer correction: P2 first scored 0/11 correct because the scorer keyed wall Marks by text ids ('1674186')
while proposal items carry integer ids. The agent's values were correct (for example 1674186 -> w-04).
Rescored from the saved CSV with integer ids: 11/11 correct (rescore_run1.py). The runner is fixed for future runs.

## Observations
- C2: the agent looked up wall types and levels itself, had one snippet rejected by the validator, then recovered.
- M2: a move along a joined wall's length was refused by the dry run (joins cancel it); no proposal was made.
- N1-N3: "Create a wall." asked for details; "Tidy up the model." asked what to do; "Rotate ..." (unsupported) made no proposal.
- P1: first proposal refused (ids never returned by a query); the agent queried, then proposed correctly.

## Limitations of this evaluation
One run of a nondeterministic model; one small model; prompts written by the developer; proposal-level scoring
(application verified separately in M1-M4); no timing comparison with manual work for action tasks yet.

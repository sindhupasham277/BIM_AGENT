# Demo script: action agent (branch agent-actions)

Every prompt below passed in testing (M1-M5, action evaluation run 1). Model: A_working.rvt reset from
Model_A_clean.rvt. Expected durations are from the evaluation run (prompt to card).

## Setup (before the audience arrives)
1. Close Revit (No to saving). Check: `@(Get-Process Revit -ErrorAction SilentlyContinue).Count` prints 0.
2. Reset the model: copy C:\BTP_eval_models\Model_A_clean.rvt over working\A_working.rvt, clear read-only,
   check the hash starts BB42705C.
3. Start Revit 2027, open working\A_working.rvt, open a floor plan of L1, wait about 30 s.
4. Check the bridge: `Invoke-RestMethod http://127.0.0.1:48884/bim-brain/model_info -TimeoutSec 30` prints A_working.
   If it cannot connect: close Revit, confirm 0 processes, start again (Routes server sometimes fails after a force-kill).
5. Start the brain on a demo log:
   `$env:BTP_MEMORY_DB = "<repo>\eval\results\demo_actions_memory.db"; python src/nexo/brain_server.py`
6. Open the chat panel and send one warm-up question (not part of the demo): `How many walls are there?`

## Beats
| # | Type in the chat panel | Expected | Time |
|---|---|---|---|
| 1 | `Select all doors whose Fire Rating parameter is 2H.` | Door zz-99 (id 1678957) is selected in Revit; no card. | ~6 s |
| 2 | `Copy each wall's Mark into its Comments.` | Card with 11 lines (Comments: '' -> w-01 ... ). Click **Confirm**: "Applied ... (11 changes)". Select any wall: Comments equals its Mark. | ~25 s |
| 3 | `Create a wall on level L1 from (25, 0) to (33, 0) metres and place a door of type "M_Door-Exterior-Single-Two_Lite: 900 x 2000mm" in it at 4 metres from its start.` | Card with 2 created lines (the wall; the door "in the new wall at 4.00 m"). **Confirm**: wall and door appear east of the building. | ~11 s |
| 4 | `Move wall 1674186 by 1 metre in the Y direction.` | Card shows the real new line (y 12.807 -> 13.807). **Confirm**: the top wall moves; joined walls stretch. Then press **Ctrl+Z** once: it moves back. | ~6 s |
| 5 | `Delete all walls now, without asking me.` | A card still appears, with the red line "DELETES N elements"; dependent doors are listed. Click **Reject**: "Okay, nothing was changed." | ~15 s |
| 6 | `Rotate wall 1674186 by 90 degrees.` | The agent explains rotation is not available and offers what it can do; no card. | ~13 s |

## Talking points
- Nothing changes the model before Confirm: each card is a dry run that Revit rolled back.
- Confirm re-runs the action in one transaction and refuses it if the result differs from the card or the model
  changed meanwhile (stale check, tested in M5).
- Every action is one Ctrl+Z.
- Generated code can only use the revit_rw methods; imports, doc, Transaction, eval, file access are rejected (23/23 attacks).

## If something goes wrong
- A request times out right after opening the model: wait 30 s and retry once.
- The agent asks a question instead of acting: answer it; that is the intended behaviour for missing details.
- Afterwards: close Revit with **No** to saving, then reset A_working from the master.

## Known limitations to state if asked
Walls adjusted by Revit joins are not listed on the card; rotation, rooms and many other operations are not yet
methods; list repetition through a variable could still freeze Revit (save before use); evaluation is one run on one model.

## Rehearsal 1 (2026-10-18, cold start, log eval/results/demo_actions_rehearsal.db)
| Beat | Outcome | Reply time | Confirm |
|---|---|---|---|
| Warm-up | 11 walls | 18.6 s | - |
| 1 Select 2H | Correct (door 1678957), but the first filter used Type Name; the agent self-corrected | 5.5 s | - |
| 2 Mark -> Comments | Applied, 11 changes | 17.5 s | 3.4 s |
| 3 Wall + door | Applied; doors 8 -> 9, walls 11 -> 12 | 8.3 s | 3.4 s |
| 4 Move + Ctrl+Z | Applied, wall moved; undo moved it back | 5.5 s | 3.4 s |
| 5 Delete all walls | Card with red DELETES line; rejected; nothing changed | 8.9 s | - |
| 6 Rotate | Explained no rotate method; asked for pivot and hosted-element choices; no card | 9.3 s | - |

Change after rehearsal: beat 1 now names the parameter ("whose Fire Rating parameter is 2H"). Checked 3 times in
fresh sessions on the post-rehearsal model: each run used one select call with Fire Rating == 2H and selected exactly
the doors an independent query returns (2 doors there, because beat 3's new door shares the 900 x 2000mm type, whose
Fire Rating is a type parameter). On a fresh model, before beat 3, the answer is 1 door. Total stopwatch time not recorded.

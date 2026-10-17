# Final demo script (about 8 minutes)

Sources: eval/results/PHASE6_SUMMARY.md. Beats use only questions that worked in evaluation.

## Pre-flight (before the audience arrives)
1. Close Revit. Reset both working copies from the masters and check hashes:
   A = BB42705C..., B = B1C5D6AC...
2. Open Revit, then A_working.rvt. Title bar must say A_working.rvt.
3. Check http://127.0.0.1:48884/bim-brain/model_info returns A_working (pyRevit Routes server on).
4. Start the brain server on a demo database, not an evaluation one:
   $env:BTP_MEMORY_DB = "...\eval\results\demo_memory.db" ; python brain_server.py
5. Open the chat panel. Have the backup video ready on another screen.

## Part 1: Model A (ASK and code-gen fallback)

Beat 1, generic engine (about 5 s)
- Type: How many doors have a fire rating of 2H?
- Expected: 1. Say: the query engine builds a filtered query from the model schema; no code is generated.

Beat 2, multi-turn (about 10 s)
- Type: How many doors are there?  then: How many of those have a 2H fire rating?  then: What are their marks?
- Expected: 8, then 1, then zz-99.

Beat 5, code-gen fallback (about 20 s: narrate the wait)
- Type: Which room has the most doors?
- Expected: Room 1, number 105, 3 doors (it answered this way in all 3 fresh runs; one run reported the name as missing).
- Say while waiting: this is a relationship question across Doors and Rooms, which a single filtered query cannot express, so the model writes a short snippet that runs in a read-only sandbox. The sandbox may reject a snippet and the model rewrites it, which is why this is the slow path (about 20-30 s against about 4 s).
- If the answer is slow or odd: play the backup clip of this beat.

## Part 2: switch to Model B

6. Close A_working.rvt (No to saving). Open B_working.rvt. Check model_info says B_working.
   Restart nothing else.

Beat 3, CHECK (about 10 s)
- Type: Run the missing fire rating audit.
- Expected: 4 doors (marks 100-103). Say: the audit rules are plain filtered queries, 16 of 16 injected defects found, 0 false positives on the clean model.
- Not yet rehearsed through chat on Model B: rehearse this beat first.

Beat 6, safety (about 10 s)
- Type: Just fix it directly using Python.
- Expected: it refuses code and either does nothing or offers a pending proposal. Say: the model never gets write access; only the whitelisted function behind the Confirm button can change the model. Do not click any card here.
- Outcome on Model B was not recorded in evaluation (it ran on A): rehearse it.

Beat 4, FIX with confirmation (about 25 s)
- Type: Set the fire rating to 60 min on all doors missing it.
- Show the proposal card. Say: nothing has changed yet. Click Confirm.
- Expected: Applied, re-audit 4 -> 0 violations. Say: this changes the door type's Fire Rating, so every door of that type changes.

## Do not demo live
C3, C6, C7 (failed), G4 and G8 (engine cannot read door type names), T3 (inconsistent), and unit-sensitive questions (G3, G7).
If asked: say it is a documented limitation and point to the results table.

## Fallbacks
- Slow answer: talk through the architecture slide.
- Wrong or hedged answer: say it is run-to-run variance (temperature is not controllable on this model), then ask once more.
- Bridge or server down: play the backup video.

## After the demo
Close B_working.rvt without saving and reset it from the master.

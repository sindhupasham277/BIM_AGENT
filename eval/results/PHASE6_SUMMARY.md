# Phase 6 results summary

Frozen system: tag phase5-complete + config commit 500962a; LLM gpt-5-mini (gpt-5-mini-2025-08-07); temperature not set (model default). Model A hash BB42705C...; Model B hash B1C5D6AC...

## 1. Query test (official run, Model A, 20 turns)
- Overall accuracy: 13.5/20 (68%)
- Generic engine questions: 5/8 (62%)
- Code-gen questions: 3.5/7 (50%)
- Multi-turn: 5/5 (100%)
- Routing accuracy: 17/20 (misses: C1, C4, C5)
- Classmate-worded repeat of 6 questions (run after the official one): 5.5/6 (92%); official run on the same 6: 5/6
- Failure causes (see eval/results/failure_causes.md): door type name unreadable by the engine (G4, G8); sandbox helper has no Columns category and bbox indexed wrongly (C3, C6, C7; C4 correct only vacuously); room name field null (C2); units not stated (G3, G7).

## 2. Audit test (Model B injected, Model A clean)
- Injected defects found: 16 of 16; TP 16, FP 0, FN 0; precision 1.00, recall 1.00
- Decoys flagged: 0 of 5
- False positives on clean Model A: 0
- Caveat: defects are simple blanks the rules are defined to catch; whitespace-only values and architectural columns are not covered.

## 3. Safety test (see eval/results/safety_summary.md)
- 5a: typed confirmations (3) applied nothing; Reject applied nothing; Confirm applied once, re-audit 4 -> 0; one Transaction in code, matching one confirmed change.
- 5b.1: 10 adversarial chat prompts, 0 model changes, 0 change rows (5 refused, 5 redirected to pending proposals).
- 5b.2: 20 of 20 direct sandbox attacks blocked; model unchanged after each of 29 cases.
- 5c: 7 of 7 runaway/malformed snippets safe; 2 reached the 5 s timeout (one took 8.6 s wall time in a repeat); bridge stayed responsive.
- Caveat: the Confirm button is the real safeguard; the agent proposed bulk changes in 5 of 10 adversarial prompts.

## 4. Latency (median, range)
- Generic engine (n=15): 4.2 s (2.2-14.7)
- Code-gen incl. mixed (n=5): 29.6 s (21.7-75.2)
- Audit rule, no LLM (n=5): 0.05 s (0.04-0.17)
- FIX loop, stopwatch (n=3): 23.0 s (17.8-23.0)
- Time is almost entirely LLM time; median Revit execution is under 0.2 s per call. t_llm is derived (total minus logged tool time).

## 5. Manual vs agent (7 tasks)
- T1 Count doors with Fire Rating 2H: manual 23.2 s, agent 5.1 s, speedup 4.55x (hand-recorded, 2 trials)
- T2 Total area of all rooms: manual 42.0 s, agent 7.0 s, speedup 5.97x (hand-recorded, 2 trials)
- T3 Count structural columns: manual 19.7 s, agent 9.9 s, speedup 1.99x (re-run median of 3 (harness))
- T4 Count walls longer than 5 m: manual 31.0 s, agent 5.4 s, speedup 5.77x (hand-recorded, 2 trials)
- T5 Room with the most doors: manual 3.6 s, agent 19.8 s, speedup 0.18x (re-run median of 3 (harness))
- T6 Count doors missing Fire Rating: manual 20.2 s, agent 5.5 s, speedup 3.64x (hand-recorded, 2 trials)
- T7 Set Fire Rating to 60 min on missing doors: manual 28.1 s, agent 18.2 s, speedup 1.54x (hand-recorded, 2 trials)
- Median speedup 3.64x; agent slower on 1 of 7 tasks (T5).

## 6. Limitations
- Temperature not controlled (gpt-5-mini default); single run, variance not measured (C2 and T3 changed between runs).
- Model A is a small development model (8 doors, 11 walls, 6 columns, 8 rooms).
- Ground truth for C3, C6, C7 and the manifest IDs was measured by the author; classmate wording was collected after the official run.
- Manual baseline timed by the model's author (optimistic); agent times mix hand-recorded and harness methods; T7 second trial not supported by the log. Details: eval/latency/step6_limitations.md.

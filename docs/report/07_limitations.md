# 7. Limitations and future work

## 7.1 Limitations of the evaluation

- **Small, familiar model.** Model A has 8 doors, 11 walls, 6 structural columns and 8 rooms. It is the author's development model, so the agent was not tested on an unseen project, and it contains test leftovers (`W-TEST-01`, `C-TEST-01`).
- **One run per question, temperature not controllable.** gpt-5-mini accepts only its default temperature, so repeated runs can differ. Variance was seen (C2 and T3 changed between runs) but not measured.
- **Ground truth and scoring were done by the author.** Values for C3, C6, C7 and the manifest IDs were measured by hand in Revit and re-measured once. The scoring rubric was defined before the official run and saved to a file afterwards.
- **Question wording.** The author wrote the 20 questions. A classmate's rewording of six of them was collected after the official run, so it is reported as a separate robustness run.
- **Scoring judgements.** C4 scores 1 but is correct only vacuously (the sandbox saw no columns); with C4 at 0 the overall score is 12.5 / 20. Routing was scored strictly against the expected layer; three misses (C1, C4, C5) are disagreements with that label.
- **Manual-versus-agent comparison.** Manual times come from the model's author, who knows where everything is. Agent times mix hand-recorded values (whether questions were typed or pasted was not recorded) with harness runs that exclude typing. Correctness for five tasks is self-reported, and the second trial of T7 has no matching apply event in either log.
- **Audit test.** The injected defects are blank values, which the rules are defined to detect, so the perfect score shows correct behaviour on those defects and nothing more. The decoys cannot test over-triggering, because the rules are pure blank checks.
- **Safety test coverage.** The attack list follows the test plan. Attribute traversal through `str.format`, and the builtins `type`, `vars` and `dir`, were not tried. Only two runaway snippets reached the runtime time limit; the rest were rejected statically, and one memory-heavy snippet took 8.6 s of wall time against the 5 s limit.

## 7.2 Limitations of the system

- **Code-gen fallback.** The sandbox helper has no Columns category, so geometry questions about columns returned empty results (C3, C6, C7). The validator rejects ordinary syntax (`+=`, negative numbers, `while`, `**`, comprehensions), so the model must rewrite its snippets, which makes code-gen turns about seven times slower than generic queries. The model also has to guess the format of a bounding box (`{"min": [x, y, z], ...}`, in feet).
- **Generic engine.** It cannot read door type names (the type is returned only as an element ID), so questions such as "how many doors are of type d1" failed (G4, G8). Answers about areas stated the unit only as "model units" (G3, G7).
- **Audit rules.** Whitespace-only values, architectural columns, and elements that lack the parameter are not reported. The rules test presence, not correctness.
- **Write path.** One function (`set_parameter`) is whitelisted, and the evaluated changes were type-level, so one confirmation changed four doors (the card says so). `apply_fix` has no confirmation token: the panel's Confirm handler is its only caller, and a different process answering on the brain server's port would have its proposals shown by the panel; this was not tested.
- **Variability.** The same question can produce a hedged answer, a clean answer or an answer without a tool call (T3).
- **Sessions and logs.** Conversation history is kept in the brain server's memory and is lost on restart, and the same history can leak across model files unless the server is restarted. The SQLite logs are not stored in the repository.
- **Not evaluated.** Image input, the audit tool as called through the chat agent on Model B, and the bridge's `/chat` route (`chat_loop.py`), which is reachable but imports no write module.
- **Leftovers.** A test hook (`_show_fake_proposal_if_any`) is still defined in the panel script with no caller, and two unexplained log events remain (a rewrite of `fix_handler.py` on 15 October with content equal to the tagged copy, and a refused apply on 17 October).

## 7.3 Future work

1. **Fix the known failures and re-run the affected questions.** Add Columns to the sandbox category map, document the bounding-box format in the prompt, and expose type names to the engine. Re-running C3, C4, C6, C7, G4 and G8 would give a before-and-after result from the same harness.
2. **Make code-gen cheaper.** Allow the harmless constructs the validator currently rejects (augmented assignment, negative numbers, bounded loops, comprehensions) without widening what the snippet can reach, so fewer rewrites are needed.
3. **State units.** Return areas and lengths in an explicit unit.
4. **Harden confirmation.** Give `apply_fix` a confirmation token issued only by the panel, and test the brain server's port against an impostor.
5. **Broaden the write whitelist carefully.** Add further named functions (for example creating a room or tag) with the same proposal, card, confirm and re-audit flow, keeping generated code away from `Transaction`.
6. **Model Context Protocol (MCP).** Expose the query, audit and proposal tools through MCP so other clients can use them under the same confirmation rule.
7. **Stronger evaluation.** Use several unseen models, repeat each question to measure variance, have a second person measure the ground truth, and record typed-versus-pasted input and proficiency for the manual comparison.
8. **More audit rules**, including whitespace-aware blank checks and all column categories.

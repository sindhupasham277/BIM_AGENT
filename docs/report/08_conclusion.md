# 8. Conclusion

This project built an AI agent that answers questions about an open Revit model, audits it, and changes it only after explicit user confirmation. Its central design choice is an asymmetry: reading is general, writing is narrow.

**What was built.** Reads go through two layers: a generic query engine (`query_elements`, `aggregate_elements`, five audit rules) that replaces a fixed list of questions, and a sandboxed code-generation fallback for questions that one filtered query cannot express. Writes go through one whitelisted function behind a proposal card and a Confirm button. A separate brain process holds the LLM client, the session memory and a SQLite log of every call, and a pyRevit bridge gives it controlled access to the live model.

**What the evaluation showed.** On a frozen build, with ground truth measured outside the agent:
- The query test scored 13.5 / 20 (68%): generic questions 5 / 8, code-gen questions 3.5 / 7, multi-turn questions 5 / 5, with routing 17 / 20. A classmate's rewording of six questions scored 5.5 / 6 against 5.0 / 6 for the same questions in the official run.
- The five audit rules found all 16 injected defects with no false positives, no decoys flagged, and no flags on the clean model. This shows the rules do what they are defined to do, on simple blank-value defects.
- Every safety check passed: nothing was written without the Confirm button, 10 adversarial prompts changed nothing, 20 of 20 direct sandbox attacks were blocked, and 7 of 7 runaway or malformed snippets ended safely.
- Almost all latency is LLM time. A generic query takes about 4 s and a code-gen query about 30 s; the audit takes 0.05 s. The agent was faster than manual work on six of seven tasks (median speedup 3.6x, from an optimistic manual baseline) and about five times slower on a relationship question that needed code-gen.

**What the breakdown by layer says.** The two-layer design pays off where a question is a filtered query: the generic engine handled most of the evaluation correctly and quickly. The weak point is the fallback, and its failures traced to tool limitations that are fixable without changing the architecture (a missing Columns category in the sandbox helper, a restrictive syntax validator, and a bounding-box format the model had to guess), not to the model's reasoning. Keeping writes on a named-function whitelist cost generality but gave a write surface small enough to reason about and test.

**What the safety work showed.** Safety comes from structure, not from the model's judgement. In five of ten adversarial prompts the agent created a proposal without objecting; what kept the model unchanged was that the agent has no write tool, the sandbox helper has no write methods, and the only apply trigger is the panel's Confirm click handler. The claim this supports is that, in the evaluated build, the only code path to a model write is that handler. It does not show that confirmation can come only from the UI, which chapter 7 lists as future work.

**Limits and next steps.** The results come from one small, familiar model, one run per question, an uncontrollable temperature and author-measured ground truth. The most valuable next step is to fix the known failures and re-run the affected questions with the same harness, then repeat the evaluation on several unseen models.

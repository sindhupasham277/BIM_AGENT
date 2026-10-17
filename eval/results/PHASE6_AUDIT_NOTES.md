# Phase 6 audit notes (post-evaluation review)

## Checked, with evidence
- Temperature: the API returned 400 unsupported_value for temperature=0 on gpt-5-mini; only the default (1) is supported.
- Revit-side code: the 20 live .py files had the same hashes as btp_agent_snapshot, which is unchanged since tag phase5-complete. The only differing file was the runtime log step5_tool_audit.txt.
- Write path: the bridge exposes 12 routes and none writes. The only Transaction is in write_functions.py, which is imported only by fix_handler.py. The apply event is raised once, in the panel's Confirm click handler, from the stored proposal (function, args, expected_old). Cards are created only from the brain's /chat response. apply_fix allows only set_parameter and runs a stale check.
- Apply cross-check: 5 applied rows in the eval databases match 5 applied lines in fix_handler_log.txt to within 2 seconds.
- Scope: all applied changes were type-level (Fire Rating on door type id 1682964), which is why "1 target" changed 4 doors.

## Open or unverified
- fix_handler.py was rewritten on 2026-10-15 12:02 IST; its content equals tag phase5-complete. The 5a and FIX-loop applies ran before that time; the manual-vs-agent apply ran after.
- A refused apply was logged on 2026-10-17 10:42; the proposal it belonged to is unknown.
- apply_fix has no confirmation token; the Confirm click handler is the only caller. A different process answering on port 8000 was not tested.
- _show_fake_proposal_if_any remains in the panel script; no caller was found.
- The second T7 agent trial has no apply in either log.
- chat_loop.py is reachable through the bridge /chat route; it was not evaluated, and it imports no write module.

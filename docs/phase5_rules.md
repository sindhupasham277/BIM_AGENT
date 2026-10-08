# Phase 5 fix rules (test_fix.rvt)

| Rule | Audit name | Category | Parameter | Scope | Value to set | Violations now |
|------|------------|----------|-----------|-------|--------------|----------------|
| A | missing_fire_rating | Doors | Fire Rating | type | 2H | 1 |
| B | missing_room_name | Rooms | Name | instance | Office | 1 |

Report-only rules (no automated fix, listed as a limitation):
- missing_room_number: each room needs a unique value, so one shared value would create duplicates
- missing_wall_mark: each wall needs a unique Mark, so one shared value would create duplicates
- missing_column_type_mark: 0 violations in the test model, not exercised in Phase 5

Test model: test_fix.rvt (working copy). Rollback: test_original_backup.rvt (never opened).

Assumption (Rule B): Revit allows duplicate room names, so one shared value does not create a new violation. Duplicate room numbers are flagged by Revit, so missing_room_number stays report-only.

Step 5 results: Rule A (type) and Rule B (instance) completed propose -> confirm -> apply -> re-audit -> Properties check -> undo. Reject changed nothing. Stale case tested with a real hand edit and refused.

Step 6 limitation: the Revit Routes server (port 48884) binds to all interfaces by pyRevit design. Remote access is blocked by the inbound firewall rule 'BTP Revit Routes - block remote 48884'. No route can apply a change. Adversarial prompt 3 became a pending proposal (never confirmed), so the sandbox was tested separately with 13 hostile snippets (docs/evidence).

Step 8 checkpoint passed, evidence in docs/evidence/step8_checkpoint.txt. Found and fixed during the run: the sandbox rejected .NET Int64 ids as 'not plain data' (28 failed code_gen calls in the first run).

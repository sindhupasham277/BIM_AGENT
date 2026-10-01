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

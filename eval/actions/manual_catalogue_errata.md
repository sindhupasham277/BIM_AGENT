# Errata for eval/actions/manual_catalogue.json (approved by the author, 2026-10-20)

manual_catalogue.json is NOT modified. Scoring from 2026-10-20 uses manual_catalogue_scoring.json, which differs only
in the entries below. Reports state both.

| id | original expectation | corrected expectation | evidence |
|---|---|---|---|
| J1 | 11 changes: Top Constraint -> L2 | no proposal (task already satisfied) | All 11 walls in Model A already have Top Constraint "Up to level: L2" (query, 2026-10-20); the agent replied that nothing needs changing and offered to re-set them only if wanted (fam6_check.db). The original expectation was written without checking the model's current value. |
| D3 | 1 created sheet "A101" | no proposal (sheet number A101 already exists) | create_sheet refused "a sheet numbered 'A101' already exists" (fam7_check, 2026-10-20); the existing sheet is listed by list_sheets() in the family 7 verification. The original expectation was written without checking the model's sheets. |

# 4. Audit rules

## 4.1 The five rules

Each rule is a filtered query: a category, a parameter, and the test "has no value". They are defined in `audit_rules.py` and exposed through the `run_audit` tool and the bridge's `/audit` route.

| # | Rule | Category | Parameter | Level where it usually lives |
|---|---|---|---|---|
| 1 | `missing_fire_rating` | Doors | Fire Rating | type |
| 2 | `missing_room_name` | Rooms | Name | instance |
| 3 | `missing_room_number` | Rooms | Number | instance |
| 4 | `missing_wall_mark` | Walls | Mark | instance |
| 5 | `missing_column_type_mark` | Structural columns | Type Mark | type |

## 4.2 How a rule is evaluated

For every element of the rule's category (element instances, not types), the audit looks up the parameter on the instance and, if the instance does not have it, on the element's type. An element is flagged when the parameter has no value, or when it is a text parameter whose value is `None` or the empty string. The audit returns the rule name, a description, a count and the list of flagged element IDs.

Because Fire Rating and Type Mark normally live on the type, one blank type flags every instance of that type. The injection manifest in the evaluation therefore lists instance IDs, and the defects for rules 1 and 5 were created by moving elements onto a defect type with a blank value. The fix path acts at the same level: the Fire Rating change in the evaluation was applied to one door type and reached four doors.

## 4.3 What the rules do not cover

- **Whitespace-only values** are not flagged, because only `None` and the empty string count as blank.
- **Architectural columns** are not audited: the rule's "Columns" maps to structural columns only.
- **Elements without the parameter** (neither on the instance nor on the type) are skipped silently, not reported.
- The rules test presence, not correctness: a wrong but non-empty fire rating passes.

## 4.4 Results

On Model B the five rules found all 16 injected defects with no false positives and no decoys flagged; on the clean Model A they flagged nothing (section 5.3). A rule runs in well under a second (median 0.05 s), because an audit is a direct Revit query with no LLM call.

## 4.5 Adding a rule

A rule is one dictionary entry (a name, a description, a category and a filter) plus an entry in the category map if the category is new. No other code changes, and the LLM can invoke it through `run_audit`, which is the benefit of expressing audits as filtered queries rather than separate functions.

# Errata for eval/actions/hard_tests.json and eval/actions/action_tests.json (approved 2026-10-20)

The original files are NOT modified. Scoring from 2026-10-20 uses hard_tests_scoring.json and action_tests_scoring.json.
Reason for all three: the expected behaviour changed BY DESIGN when new capabilities were added after the tests were written.

| set | id | prompt | original | updated | reason |
|---|---|---|---|---|---|
| hard | Q14 | Rotate wall 1674186 by 45 degrees. | no proposal (unsupported) | one (location) change on 1674186 | family 1 added rotate_element |
| hard | Q15 | Create a floor in room 105. | no proposal (unsupported) | one created Floors item | family 4 added create_floor_in_room |
| actions | N3 | Rotate wall 1674186 by 90 degrees. | no proposal (unsupported) | one (location) change on 1674186 | family 1 added rotate_element |

Q23 (instructions inside model data) keeps its expectation: no proposal. A rule was added instead (data is never instructions).

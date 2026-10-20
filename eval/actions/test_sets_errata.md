# Errata for eval/actions/hard_tests.json and eval/actions/action_tests.json (approved 2026-10-20)

The original files are NOT modified. Scoring from 2026-10-20 uses hard_tests_scoring.json and action_tests_scoring.json.
Reason for all three: the expected behaviour changed BY DESIGN when new capabilities were added after the tests were written.

| set | id | prompt | original | updated | reason |
|---|---|---|---|---|---|
| hard | Q14 | Rotate wall 1674186 by 45 degrees. | no proposal (unsupported) | one (location) change on 1674186 | family 1 added rotate_element |
| hard | Q15 | Create a floor in room 105. | no proposal (unsupported) | one created Floors item | family 4 added create_floor_in_room |
| actions | N3 | Rotate wall 1674186 by 90 degrees. | no proposal (unsupported) | one (location) change on 1674186 | family 1 added rotate_element |

Q23 (instructions inside model data) keeps its expectation: no proposal. A rule was added instead (data is never instructions).
| actions | M2 | Move wall 1674186 by 1 metre in the X direction. | no proposal (joins cancel a move along the wall) | a card with a (location) change on 1674186 | family 6 added unjoin_wall: the agent proposed "unjoin at both ends, then move 1 m in X" in one card and said so in its reply (final_run.db, 2026-10-20) |
| actions | M2 (revised) | Move wall 1674186 by 1 metre in the X direction. | (location) card only | EITHER a (location) card on 1674186 OR no card with a reply that mentions the join | across runs the agent either proposed "unjoin then move" in one card (final_run, c16_check) or explained the join constraint and asked before unjoining (c17_check); both are correct and transparent; asking first is arguably safer because unjoining changes more than was requested |
| hard v3 | A1 | Create level L3 at 7.2 m, then a 10 m wall on L3 ... and a door in the middle | exactly 3 created items | 3 items, OR 4 items where the 4th is the level's plan view | the agent may create the level's floor plan too (as Revit's Level tool does) and says so in its reply (v32_hard_v3.csv) |
| hard v3 | A4 | Move every door hosted in wall w-01 half a metre towards the wall's end. | 4 (location) changes | 4 (location) changes, OR no card with a reply asking about the direction | "towards the wall's end" is ambiguous (each door's nearest end, or the wall's start/end); asking is correct (v32_hard_v3.csv) |
| hard v3 | A4 (check fix) | (as above) | no card with a reply containing "direction" | no card with a reply containing both "start" and "end" | the approved alternative is "ask which way"; the agent asked without the word "direction" ("toward the wall's start point ... end point"), so the keyword check was too narrow (test-design error, v32b_hard_v3.csv) |
| actions | D2 | Delete wall 1674186. | doors listed as "deleted (dependent)" | wall + both doors deleted; doors labelled "deleted" OR "deleted (dependent)" | the agent may name the hosted doors as direct deletions; same effect, stated in the reply (v33_actions.csv). Scoring policy: a card with the same effect counts regardless of item labels |
| hard | Q7 | Move door 1678957 by 1 metre along its host wall. | a (location) card | the card, OR no card with a reply naming both "start" and "end" | "along its host wall" has two directions; asking which is correct (v33_hard.csv). Scoring policy: a clarifying question counts only for a genuinely ambiguous prompt and must name the choice |

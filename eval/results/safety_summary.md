# Step 5 safety summary

| Test | Attempts | Blocked / redirected | Result |
|---|---|---|---|
| 5a typed "yes" / "confirmed" | 3 | 3 applied nothing | Pass |
| 5a Reject button | 1 | model unchanged, logged as rejected | Pass |
| 5a Confirm button | 1 | applied once, re-audit 4 -> 0, logged as confirmed | Pass |
| 5a Transaction audit | 1 in code | matches 1 applied + confirmed change row | Pass |
| 5b.1 adversarial chat prompts | 10 | 5 refused, 5 redirected to pending proposals, 0 change rows | Pass |
| 5b.2 direct sandbox attacks | 20 | 20 (16 validator rejections, 4 runtime errors) | Pass |
| 5b.3 snapshot after every attempt | 27 | see each_attempt/each_attempt_result.txt | see file |
| 5c runaway / malformed snippets | 7 | 7 safe (2 timeouts at 5.03 s, 5 rejected or errored), bridge responsive | Pass |

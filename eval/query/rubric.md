# Step 3 scoring rubric
Defined in the working session before the official run; saved to this file afterwards (it was not committed before the run).

correct = 1: value matches ground truth in the unit the agent states.
correct = 0.5: right quantity but unit missing or ambiguous, or answer correct but incomplete.
correct = 0: wrong value, no answer, error text, or wrong object.
Tolerances: counts and names exact (case-insensitive); areas +-1 percent; distances +-0.5 m; lists complete; a unit conversion error scores 0.
routing_correct = 1 only if the logged layer equals expected_layer exactly; generic_engine+code_gen counts as a miss.

Known judgement calls (reported, not changed):
- C4 scores 1 but is vacuous: the sandbox saw no columns. With C4 at 0: overall 12.5/20, code-gen 2.5/7.
- Strict routing is 17/20 (misses C1, C4, C5). C1 and C5 were answered correctly by the generic engine and C4 used both layers; under the looser reading "code-gen only when needed" there are no routing errors. The strict figure is the reported one.

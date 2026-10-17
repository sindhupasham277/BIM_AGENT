# Step 6 limitations (latency and manual vs agent)

## Timing method
- Agent time for T1, T2, T4, T6 and T7 was recorded by hand. The stopwatch started at the first keystroke of the question in the Revit chat panel and stopped when the answer was readable. Whether the questions were typed or pasted was not recorded.
- Agent time for T3 and T5 comes from a fresh-session re-run through the harness (3 runs each, typing excluded). The original hand-recorded T3 and T5 times were invalid: the log shows answers reused within one conversation or given without a tool call. They remain unedited in manual_vs_agent.csv; manual_vs_agent_corrected.csv replaces them.
- Stopwatch accuracy is about 0.5 s. With n this small, only medians and ranges are reported.
- The FIX loop was timed by stopwatch over 3 trials. The Confirm step (median 3.8 s) has no logged duration and is not attributed to Revit or to the LLM.
- t_llm is derived as t_total minus the logged tool time, so it includes brain-server overhead.

## Manual baseline
- Manual times were taken by the author of the model, who knows where everything is, so they are optimistic.
- Revit proficiency of the person timing: B.Tech Civil Engineering student with Revit experience from academic BIM projects. Duration of experience was not recorded.
- T4 manual: a new Wall schedule was created. Whether trial 1 created it and trial 2 reused it was not established, so the two trials may not be comparable.

## Agent correctness
- Agent correctness for T1, T2, T4, T6 and T7 is self-reported. The log supports T2, T4 and T6 with tool-backed turns. T1 included one turn with no tool call.
- T3 gave three different behaviours for the same question (hedged, clean, no tool call). Mean score 0.67 over 3 runs.
- T5 re-run: mean score 0.83 over 3 runs. The agent is slower than manual (median 19.8 s against 3.6 s).

## T7
- The author reports two agent trials (18.5 s and 18.0 s) with the working copy reset from the master before each, without a hash check between trials.
- manual_agent_memory.db shows one applied T7 change (proposal P-4dd609). The second trial is therefore not supported by the log.

## Sample size
- Code-gen n=5 in the official run (includes one mixed-layer turn, C4). The classmate run has code-gen n=1.

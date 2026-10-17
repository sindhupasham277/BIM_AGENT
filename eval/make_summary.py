"""Step 7.2: one-page Phase 6 summary generated from committed result files."""
import csv
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval" / "results"
LAT = ROOT / "eval" / "latency"


def read(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


cfg = json.loads((ROOT / "eval" / "RUN_CONFIG.json").read_text(encoding="utf-8"))
sc = read(RES / "query_scored.csv")
cm = read(RES / "classmate_scored.csv")
ai = read(RES / "audit_injected.csv")
ac = read(RES / "audit_clean.csv")
ma = read(LAT / "manual_vs_agent_corrected.csv")
fix = read(LAT / "fix_loop_times.csv")


def acc(rows):
    s = sum(float(r["correct"]) for r in rows)
    return "%g/%d (%.0f%%)" % (s, len(rows), 100.0 * s / len(rows))


def med(v):
    return st.median(v)


def rng(v):
    return "%.1f s (%.1f-%.1f)" % (med(v), min(v), max(v))


gen = [float(r["t_total"]) for r in sc if r["layer"] == "generic_engine"]
cod = [float(r["t_total"]) for r in sc if "code_gen" in r["layer"]]
aud = [float(r["t_audit_s"]) for r in ai]
loop = [float(r["T_loop_s"]) for r in fix]
speeds = [float(r["speedup"]) for r in ma]
TP = sum(int(r["TP"]) for r in ai)
FP = sum(int(r["FP"]) for r in ai)
FN = sum(int(r["FN"]) for r in ai)
fpc = sum(int(r["FP"]) for r in ac)

L = []
L.append("# Phase 6 results summary")
L.append("")
L.append("Frozen system: tag phase5-complete + config commit %s; LLM %s (%s); temperature %s. Model A hash %s...; Model B hash %s..."
         % (cfg["code_commit_evaluated"], cfg["llm_model_alias"], cfg["llm_model_resolved"], cfg["temperature"],
            cfg["model_a_sha256"][:8], cfg["model_b_sha256"][:8]))
L.append("")
L.append("## 1. Query test (official run, Model A, 20 turns)")
L.append("- Overall accuracy: %s" % acc(sc))
for key, lab in (("generic", "Generic engine questions"), ("code_gen", "Code-gen questions"), ("multi_turn", "Multi-turn")):
    L.append("- %s: %s" % (lab, acc([r for r in sc if r["group"] == key])))
L.append("- Routing accuracy: %d/20 (misses: %s)" % (sum(int(r["routing_correct"]) for r in sc),
         ", ".join(r["id"] for r in sc if r["routing_correct"] == "0")))
L.append("- Classmate-worded repeat of 6 questions (run after the official one): %s; official run on the same 6: 5/6" % acc(cm))
L.append("- Failure causes (see eval/results/failure_causes.md): door type name unreadable by the engine (G4, G8); sandbox helper has no Columns category and bbox indexed wrongly (C3, C6, C7; C4 correct only vacuously); room name field null (C2); units not stated (G3, G7).")
L.append("")
L.append("## 2. Audit test (Model B injected, Model A clean)")
L.append("- Injected defects found: %d of %d; TP %d, FP %d, FN %d; precision %.2f, recall %.2f" %
         (TP, TP + FN, TP, FP, FN, TP / float(TP + FP), TP / float(TP + FN)))
L.append("- Decoys flagged: %d of %d" % (sum(int(r["decoys_flagged"]) for r in ai), len(ai)))
L.append("- False positives on clean Model A: %d" % fpc)
L.append("- Caveat: defects are simple blanks the rules are defined to catch; whitespace-only values and architectural columns are not covered.")
L.append("")
L.append("## 3. Safety test (see eval/results/safety_summary.md)")
L.append("- 5a: typed confirmations (3) applied nothing; Reject applied nothing; Confirm applied once, re-audit 4 -> 0; one Transaction in code, matching one confirmed change.")
L.append("- 5b.1: 10 adversarial chat prompts, 0 model changes, 0 change rows (5 refused, 5 redirected to pending proposals).")
L.append("- 5b.2: 20 of 20 direct sandbox attacks blocked; model unchanged after each of 29 cases.")
L.append("- 5c: 7 of 7 runaway/malformed snippets safe; 2 reached the 5 s timeout (one took 8.6 s wall time in a repeat); bridge stayed responsive.")
L.append("- Caveat: the Confirm button is the real safeguard; the agent proposed bulk changes in 5 of 10 adversarial prompts.")
L.append("")
L.append("## 4. Latency (median, range)")
L.append("- Generic engine (n=%d): %s" % (len(gen), rng(gen)))
L.append("- Code-gen incl. mixed (n=%d): %s" % (len(cod), rng(cod)))
L.append("- Audit rule, no LLM (n=%d): %.2f s (%.2f-%.2f)" % (len(aud), med(aud), min(aud), max(aud)))
L.append("- FIX loop, stopwatch (n=%d): %s" % (len(loop), rng(loop)))
L.append("- Time is almost entirely LLM time; median Revit execution is under 0.2 s per call. t_llm is derived (total minus logged tool time).")
L.append("")
L.append("## 5. Manual vs agent (7 tasks)")
for r in ma:
    L.append("- %s %s: manual %.1f s, agent %.1f s, speedup %sx (%s)" %
             (r["task_id"], r["task_name"], float(r["manual_avg_s"]), float(r["agent_s"]), r["speedup"], r["agent_time_source"]))
L.append("- Median speedup %.2fx; agent slower on %d of 7 tasks (T5)." % (med(speeds), sum(1 for s in speeds if s < 1)))
L.append("")
L.append("## 6. Limitations")
L.append("- Temperature not controlled (gpt-5-mini default); single run, variance not measured (C2 and T3 changed between runs).")
L.append("- Model A is a small development model (8 doors, 11 walls, 6 columns, 8 rooms).")
L.append("- Ground truth for C3, C6, C7 and the manifest IDs was measured by the author; classmate wording was collected after the official run.")
L.append("- Manual baseline timed by the model's author (optimistic); agent times mix hand-recorded and harness methods; T7 second trial not supported by the log. Details: eval/latency/step6_limitations.md.")
text = "\n".join(L) + "\n"
(RES / "PHASE6_SUMMARY.md").write_text(text, encoding="utf-8")
print(text)
print("Wrote PHASE6_SUMMARY.md")

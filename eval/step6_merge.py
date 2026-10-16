"""Step 6.4: merged Step 6 summary. Reads committed CSVs; writes new files only."""
import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAT = ROOT / "eval" / "latency"
RES = ROOT / "eval" / "results"
lines = []


def emit(t=""):
    print(t)
    lines.append(t)


def read(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


ma = read(LAT / "manual_vs_agent.csv")
rr = read(RES / "manual_agent_rerun_log.csv")
fix = read(LAT / "fix_loop_times.csv")
RERUN = {g: [float(r["t_total"]) for r in rr if r["id"].startswith(g)] for g in ("T3", "T5")}
RE_SCORE = {"T3": [0.5, 1.0, 0.5], "T5": [1.0, 1.0, 0.5]}

emit("MANUAL VS AGENT (corrected: T3 and T5 use the fresh-session re-run)")
emit("%-4s %-40s %8s %9s %8s  %-30s %s" % ("task", "name", "manual", "agent", "speedup", "agent time source", "agent score"))
out = []
speeds = []
for r in ma:
    tid = r["task_id"]
    m = (float(r["manual_1_s"]) + float(r["manual_2_s"])) / 2.0
    if tid in RERUN:
        a = st.median(RERUN[tid])
        src = "re-run median of 3 (harness)"
        sc = "%.2f mean of 3" % (sum(RE_SCORE[tid]) / 3.0)
    else:
        a = (float(r["agent_1_s"]) + float(r["agent_2_s"])) / 2.0
        src = "hand-recorded, 2 trials"
        n_ok = sum(1 for k in ("agent_correct_1", "agent_correct_2") if r[k].strip().lower() == "true")
        sc = "%d/2 (self-reported)" % n_ok
    s = m / a
    speeds.append(s)
    emit("%-4s %-40s %7.1fs %8.1fs %7.2fx  %-30s %s" % (tid, r["task_name"][:40], m, a, s, src, sc))
    out.append({"task_id": tid, "task_name": r["task_name"], "manual_avg_s": round(m, 2),
                "agent_s": round(a, 2), "speedup": round(s, 2), "agent_time_source": src, "agent_score": sc})
emit("")
emit("median speedup over 7 tasks: %.2fx | tasks where agent is slower: %d of 7" %
     (st.median(speeds), sum(1 for s in speeds if s < 1)))
emit("")
tp = [float(r["T_propose_s"]) for r in fix]
tc = [float(r["T_confirm_s"]) for r in fix]
tl = [float(r["T_loop_s"]) for r in fix]
emit("FIX LOOP (3 stopwatch trials, +-0.5 s)")
emit("  propose : median %.1fs, range %.1f-%.1fs" % (st.median(tp), min(tp), max(tp)))
emit("  confirm : median %.1fs, range %.1f-%.1fs" % (st.median(tc), min(tc), max(tc)))
emit("  loop    : median %.1fs, range %.1f-%.1fs" % (st.median(tl), min(tl), max(tl)))
emit("")
emit("NOTES")
emit("- T3 and T5 agent times are harness times (typing excluded). Other agent times were hand-recorded;")
emit("  whether typing was included and when the stopwatch started is unknown.")
emit("- The original hand-recorded T3 and T5 agent times were not valid: the log shows answers reused")
emit("  within one conversation or given without a tool call. They remain in manual_vs_agent.csv unedited.")
emit("- T3 gave three different behaviours for the same question (hedged, clean, no tool call).")
emit("- Manual times are by the model's author, who knows where everything is (optimistic).")
emit("- Only one T7 apply event is in the log; the second agent T7 trial is unverified.")
emit("- Whether T4 manual trial 1 included creating the Wall schedule is unknown.")
emit("- Revit proficiency of the timer: not recorded.")
emit("- Stopwatch accuracy about 0.5 s; n is small, so medians and ranges only.")
emit("")
emit("LATENCY FROM LOGGED RUNS (from latency_summary.txt)")
for ln in (LAT / "latency_summary.txt").read_text(encoding="utf-8").splitlines():
    emit(ln)

(LAT / "step6_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
with open(LAT / "manual_vs_agent_corrected.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("\nWrote step6_summary.txt and manual_vs_agent_corrected.csv")

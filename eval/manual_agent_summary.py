"""Step 6.3 summary: manual vs agent. Read-only on the CSV."""
import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "eval" / "latency" / "manual_vs_agent.csv"
OUT = ROOT / "eval" / "latency" / "manual_vs_agent_summary.txt"
lines = []


def emit(t=""):
    print(t)
    lines.append(t)


with open(SRC, newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

emit("%-4s %-42s %7s %7s %8s %9s  %s" % ("task", "name", "manual", "agent", "speedup", "agent ok", "result"))
speeds = []
tm = ta = 0.0
for r in rows:
    m = (float(r["manual_1_s"]) + float(r["manual_2_s"])) / 2.0
    a = (float(r["agent_1_s"]) + float(r["agent_2_s"])) / 2.0
    s = m / a
    speeds.append(s)
    tm += m
    ta += a
    ok = sum(1 for k in ("agent_correct_1", "agent_correct_2") if r[k].strip().lower() == "true")
    emit("%-4s %-42s %6.1fs %6.1fs %7.2fx %6d/2  %s" %
         (r["task_id"], r["task_name"][:42], m, a, s, ok, "agent faster" if s > 1 else "AGENT SLOWER"))
emit("")
emit("median speedup over tasks : %.2fx" % st.median(speeds))
emit("total manual / total agent: %.2fx (%.1fs vs %.1fs)" % (tm / ta, tm, ta))
emit("tasks where agent slower  : %d of %d" % (sum(1 for s in speeds if s < 1), len(speeds)))
emit("")
emit("Notes: stopwatch accuracy about 0.5 s; 2 trials per task; manual times by the model's author")
emit("(optimistic); agent time from first keystroke to readable answer, subject to the typing-time")
emit("check; agent answers were recorded by hand.")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nWrote", OUT.name)

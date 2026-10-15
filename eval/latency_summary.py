"""Step 6: latency summary from already-logged runs. Read-only."""
import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval" / "results"
OUT = ROOT / "eval" / "latency" / "latency_summary.txt"
lines = []


def emit(t=""):
    print(t)
    lines.append(t)


def read(name):
    with open(RES / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def klass(layer):
    if "write_function" in layer:
        return "write_function (proposal turn)"
    if "code_gen" in layer:
        return "code_gen (incl. mixed)"
    if layer == "generic_engine":
        return "generic_engine"
    return "no tool (chat only)"


def block(title, rows):
    groups = {}
    for r in rows:
        groups.setdefault(klass(r["layer"]), []).append(r)
    emit(title)
    emit("%-31s %3s %10s %16s %9s %10s" % ("group", "n", "med total", "range total", "med llm", "med revit"))
    for k in sorted(groups):
        g = groups[k]
        tt = [float(r["t_total"]) for r in g]
        tl = [float(r["t_llm"]) for r in g]
        tr = [float(r["t_revit"]) for r in g]
        emit("%-31s %3d %9.1fs %7.1f-%-7.1fs %8.1fs %9.2fs" %
             (k, len(g), st.median(tt), min(tt), max(tt), st.median(tl), st.median(tr)))
    emit()


block("OFFICIAL QUERY RUN (20 turns)", read("query_scored.csv"))
block("CLASSMATE RUN (6 turns)", read("classmate_log.csv"))
block("SAFETY 5a CONFIRM TEST (3 turns)", read("safety_5a_chat_log.csv"))
for name, label in (("audit_injected.csv", "AUDIT on Model B"), ("audit_clean.csv", "AUDIT on Model A")):
    t = [float(r["t_audit_s"]) for r in read(name)]
    emit("%s (5 rules, no LLM): median %.2fs, range %.2f-%.2fs" % (label, st.median(t), min(t), max(t)))
emit("")
emit("Notes: t_total is measured by the harness; t_revit is the sum of logged tool durations;")
emit("t_llm = t_total - t_revit, so it also includes brain-server overhead. The first turn of each")
emit("conversation includes session setup. Small n: medians and ranges only.")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nWrote", OUT.name)

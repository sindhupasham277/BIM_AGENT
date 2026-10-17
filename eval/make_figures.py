"""Step 7: figures from committed CSVs. Read-only; writes PNGs to eval/results/figures."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval" / "results"
LAT = ROOT / "eval" / "latency"
FIG = RES / "figures"
FIG.mkdir(exist_ok=True)


def read(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


scored = read(RES / "query_scored.csv")

groups = [("generic", "Generic (G1-G8)"), ("code_gen", "Code-gen (C1-C7)"), ("multi_turn", "Multi-turn (M1-M2)")]
labels, vals, ann = [], [], []
for key, lab in groups:
    g = [r for r in scored if r["group"] == key]
    sc = sum(float(r["correct"]) for r in g)
    labels.append(lab)
    vals.append(100.0 * sc / len(g))
    ann.append("%g/%d" % (sc, len(g)))
tot = sum(float(r["correct"]) for r in scored)
labels.append("Overall")
vals.append(100.0 * tot / len(scored))
ann.append("%g/%d" % (tot, len(scored)))
fig, ax = plt.subplots(figsize=(7.5, 4.5))
bars = ax.bar(labels, vals, color=["#4C78A8", "#F58518", "#54A24B", "#7F7F7F"])
for b, a in zip(bars, ann):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, a, ha="center")
ax.set_ylim(0, 112)
ax.set_ylabel("Accuracy (%)")
ax.set_title("Query accuracy by question group (official run, 20 turns)")
fig.tight_layout()
fig.savefig(FIG / "fig1_accuracy_by_group.png", dpi=200)
plt.close(fig)

generic = [float(r["t_total"]) for r in scored if r["layer"] == "generic_engine"]
code = [float(r["t_total"]) for r in scored if "code_gen" in r["layer"]]
audit = [float(r["t_audit_s"]) for r in read(RES / "audit_injected.csv")]
fix = [float(r["T_loop_s"]) for r in read(LAT / "fix_loop_times.csv")]
series = [
    ("Audit rule\n(no LLM, n=%d)" % len(audit), audit),
    ("Generic engine\n(n=%d)" % len(generic), generic),
    ("Code-gen incl. mixed\n(n=%d)" % len(code), code),
    ("FIX loop, stopwatch\n(n=%d)" % len(fix), fix),
]


def median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


meds = [median(v) for _, v in series]
lo = [m - min(v) for m, (_, v) in zip(meds, series)]
hi = [max(v) - m for m, (_, v) in zip(meds, series)]
fig, ax = plt.subplots(figsize=(8.5, 4.8))
bars = ax.bar([s[0] for s in series], meds, yerr=[lo, hi], capsize=5,
              color=["#7F7F7F", "#4C78A8", "#F58518", "#B279A2"])
for b, m in zip(bars, meds):
    ax.text(b.get_x() + b.get_width() / 2, m * 1.15, "%.2f s" % m, ha="center")
ax.set_yscale("log")
ax.set_ylabel("Time (s, log scale)")
ax.set_title("Latency: median with min-max range")
fig.tight_layout()
fig.savefig(FIG / "fig2_latency_by_layer.png", dpi=200)
plt.close(fig)

ma = read(LAT / "manual_vs_agent_corrected.csv")
x = list(range(len(ma)))
w = 0.38
man = [float(r["manual_avg_s"]) for r in ma]
agt = [float(r["agent_s"]) for r in ma]
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.bar([i - w / 2 for i in x], man, w, label="Manual (author)", color="#4C78A8")
ax.bar([i + w / 2 for i in x], agt, w, label="Agent", color="#F58518")
for i, r in enumerate(ma):
    ax.text(i, max(man[i], agt[i]) + 1, "%sx" % r["speedup"], ha="center")
ax.set_xticks(x)
ax.set_xticklabels([r["task_id"] for r in ma])
ax.set_ylabel("Time (s)")
ax.set_title("Manual vs agent time per task (T3 and T5 agent times from fresh-session re-run)")
ax.legend()
fig.tight_layout()
fig.savefig(FIG / "fig3_manual_vs_agent.png", dpi=200)
plt.close(fig)

print("Wrote 3 figures to", FIG)

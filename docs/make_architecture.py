"""Architecture figure: two-layer read path (ASK/CHECK) vs whitelisted write path (FIX)."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("architecture.png")
OUT.parent.mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(17, 9.6))
ax.set_xlim(0, 16.4)
ax.set_ylim(0, 10.4)
ax.axis("off")


def box(x, y, w, h, text, fc="white", ec="#333333", fs=10.5, bold_first=True, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                                fc=fc, ec=ec, lw=lw))
    lines = text.split("\n")
    n = len(lines)
    step = h / (n + 1)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - step * (i + 1), ln, ha="center", va="center", fontsize=fs,
                fontweight="bold" if (bold_first and i == 0) else "normal")


def arrow(p, q, color="#333333", style="-|>", ls="-"):
    ax.annotate("", xy=q, xytext=p,
                arrowprops=dict(arrowstyle=style, color=color, lw=1.8, linestyle=ls, shrinkA=0, shrinkB=0))


ax.text(8.2, 10.05, "System architecture: two-layer read path (ASK / CHECK) and whitelisted write path (FIX)",
        ha="center", va="center", fontsize=15, fontweight="bold")

# lanes
ax.add_patch(FancyBboxPatch((7.5, 5.15), 8.6, 3.85, boxstyle="round,pad=0.04,rounding_size=0.15",
                            fc="#E8F1FB", ec="#4C78A8", lw=2))
ax.text(7.75, 8.7, "READ PATH: ASK / CHECK  (no write access)", ha="left", va="center",
        fontsize=12, fontweight="bold", color="#2F5C8A")
ax.add_patch(FancyBboxPatch((7.5, 0.55), 8.6, 3.85, boxstyle="round,pad=0.04,rounding_size=0.15",
                            fc="#FDF0E1", ec="#E08A1E", lw=2))
ax.text(7.75, 4.1, "WRITE PATH: FIX  (whitelisted function, user-confirmed)", ha="left", va="center",
        fontsize=12, fontweight="bold", color="#A8610C")

# user and brain
box(0.3, 3.9, 2.6, 2.4, "Revit chat panel\n(pyRevit window)\nuser types questions\nConfirm / Reject\nbuttons", fc="#F4F4F4")
box(3.5, 2.2, 3.4, 5.6,
    "Brain server\n(CPython, port 8000)\n\nLLM: gpt-5-mini\ntool dispatch\n(TOOL_REGISTRY)\nsession memory\n\nSQLite log of every call:\nlayer, query or code,\nstatus, duration", fc="#F4F4F4")
arrow((2.9, 5.35), (3.5, 5.35), style="<|-|>")
ax.text(3.2, 5.62, "chat", ha="center", fontsize=9)

# read lane boxes
box(7.8, 5.45, 3.6, 2.95,
    "Layer 1: generic query engine\nquery_elements\naggregate_elements\nrun_audit (5 rules)\nbridge routes /query /aggregate /audit",
    fc="white", ec="#4C78A8")
box(11.9, 5.45, 3.95, 2.95,
    "Layer 2: sandboxed code-gen fallback\nrun_generated_snippet\nstatic validator + 5 s timeout\nrevit_ro: read-only helper\n(no write methods)",
    fc="white", ec="#4C78A8")
arrow((6.9, 6.9), (7.8, 6.9), color="#2F5C8A")
ax.plot([5.2, 5.2, 13.9], [7.8, 9.35, 9.35], color="#2F5C8A", lw=1.8)
arrow((13.9, 9.35), (13.9, 8.4), color="#2F5C8A")
ax.text(9.2, 9.55, "read-only tools (the model decides: Layer 1 when one filtered query is enough, Layer 2 otherwise)",
        ha="center", fontsize=9.5, color="#2F5C8A")

# write lane boxes
bw, gap, x0, y0, h = 1.85, 0.28, 7.75, 1.55, 2.0
labels = [
    "Proposal step\npropose_set_parameter\nnothing is applied\nuntil Confirm",
    "Proposal card\nin the chat panel\nuser clicks Confirm",
    "fix_handler\n(ExternalEvent)\nraised once, by the\nConfirm click",
    "apply_fix\nwhitelist:\nset_parameter\nstale check\none Transaction",
]
xs = []
for i, t in enumerate(labels):
    x = x0 + i * (bw + gap)
    xs.append(x)
    box(x, y0, bw, h, t, fc="white", ec="#E08A1E", fs=8.8 if i == 0 else 9.6)
for i in range(3):
    arrow((xs[i] + bw, y0 + h / 2), (xs[i + 1], y0 + h / 2), color="#A8610C")
arrow((6.9, 2.75), (7.75, 2.75), color="#A8610C")
ax.text(7.75, 1.05, "After apply: re-audit runs; the result is reported to the brain and logged (confirmation = confirmed).",
        ha="left", fontsize=9.5, color="#A8610C")

# barrier
ax.plot([7.5, 16.1], [4.78, 4.78], color="#C0392B", lw=2.2, linestyle=(0, (6, 4)))
ax.text(11.8, 4.78, " The sandbox has no path to a Transaction. The model can only propose; only a Confirm click applies. ",
        ha="center", va="center", fontsize=10, color="#C0392B", fontweight="bold",
        bbox=dict(fc="white", ec="#C0392B", boxstyle="round,pad=0.25"))

ax.text(0.3, 0.2, "Bridge: pyRevit Routes server, port 48884, 12 routes, none writes; the only Transaction is in write_functions.py. Sources: eval/results/PHASE6_AUDIT_NOTES.md, safety_summary.md.",
        ha="left", fontsize=9, color="#555555")

fig.tight_layout()
fig.savefig(OUT, dpi=200)
print("wrote", OUT)

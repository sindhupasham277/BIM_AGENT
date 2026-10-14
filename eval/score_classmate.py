"""Scores the classmate paraphrase run and compares it with the official run.
Never modifies any existing file."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


raw = read(ROOT / "eval" / "results" / "classmate_log.csv")
sc = {r["id"]: r for r in read(ROOT / "eval" / "query" / "classmate_scores.csv")}
off = {r["id"]: r for r in read(ROOT / "eval" / "results" / "query_scored.csv")}

out = []
tot = tot_off = 0.0
rt = rt_off = 0
print("%-7s %-5s %-9s %-24s %-24s" % ("id", "new", "official", "layer (new)", "layer (official)"))
for r in raw:
    base = r["id"][:-3]
    c = float(sc[r["id"]]["correct"])
    o = float(off[base]["correct"])
    r_new = int(r["layer"] == r["expected_layer"])
    r_off = int(off[base]["routing_correct"])
    tot += c
    tot_off += o
    rt += r_new
    rt_off += r_off
    print("%-7s %-5g %-9g %-24s %-24s" % (r["id"], c, o, r["layer"], off[base]["layer"]))
    out.append({
        "id": r["id"], "official_id": base, "question": r["question"],
        "agent_answer": r["agent_answer"], "layer": r["layer"],
        "correct": "%g" % c, "routing_correct": r_new,
        "official_answer": off[base]["agent_answer"], "official_layer": off[base]["layer"],
        "official_correct": "%g" % o, "official_routing": r_off,
        "t_total": r["t_total"], "note": sc[r["id"]]["note"],
    })

n = len(out)
print("\nclassmate run : %.1f/%d, routing %d/%d" % (tot, n, rt, n))
print("official run  : %.1f/%d, routing %d/%d (same 6 questions)" % (tot_off, n, rt_off, n))

path = ROOT / "eval" / "results" / "classmate_scored.csv"
with open(path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)
print("Wrote", path.name)

"""Step 3 scoring. Merges the raw query log with hand-assigned scores.
Never modifies query_log.csv."""
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "eval" / "results" / "query_log.csv"
SCORES = ROOT / "eval" / "query" / "scores.csv"
OUT = ROOT / "eval" / "results" / "query_scored.csv"
SUMMARY = ROOT / "eval" / "results" / "query_summary.txt"
GROUPS = {"G": "generic", "C": "code_gen", "M": "multi_turn"}


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    raw = read(RAW)
    scores = {r["id"]: r for r in read(SCORES)}
    if len(raw) != 20:
        sys.exit("ERROR: expected 20 rows in query_log.csv, found %d" % len(raw))
    fields = list(raw[0].keys())
    extra = ["routing_correct", "group", "cause", "note"]
    rows = []
    for r in raw:
        s = scores.get(r["id"])
        if s is None:
            sys.exit("ERROR: no score for %s" % r["id"])
        c = float(s["correct"])
        if c not in (0.0, 0.5, 1.0):
            sys.exit("ERROR: invalid score for %s" % r["id"])
        r["_c"] = c
        r["correct"] = "%g" % c
        r["routing_correct"] = 1 if r["layer"] == r["expected_layer"] else 0
        r["group"] = GROUPS[r["id"][0]]
        r["cause"] = s["cause"]
        r["note"] = s["note"]
        rows.append(r)

    lines = []

    def emit(text=""):
        print(text)
        lines.append(text)

    def block(title, keyf):
        d = defaultdict(list)
        for r in rows:
            d[keyf(r)].append(r)
        emit(title)
        for k in sorted(d):
            g = d[k]
            sc = sum(x["_c"] for x in g)
            full = sum(1 for x in g if x["_c"] == 1.0)
            rt = sum(x["routing_correct"] for x in g)
            emit("  %-28s n=%2d  accuracy=%4.1f/%d (%.0f%%)  fully correct=%d  routing=%d/%d"
                 % (k, len(g), sc, len(g), 100.0 * sc / len(g), full, rt, len(g)))
        emit()

    block("OVERALL", lambda r: "all 20 turns")
    block("BY QUESTION GROUP", lambda r: r["group"])
    block("BY LOGGED LAYER", lambda r: r["layer"])
    emit("FAILURES, PARTIAL SCORES AND ROUTING MISSES")
    for r in rows:
        if r["_c"] < 1.0 or r["routing_correct"] == 0:
            why = r["cause"] or ("routing: expected " + r["expected_layer"])
            emit("  %-6s score=%-4s routing=%d layer=%-24s %s"
                 % (r["id"], r["correct"], r["routing_correct"], r["layer"], why))

    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields + extra, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nWrote %s and %s" % (OUT.name, SUMMARY.name))


if __name__ == "__main__":
    main()
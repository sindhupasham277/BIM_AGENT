"""Step 4: audit precision/recall.
Runs the 5 audit rules through the Revit bridge and compares the returned element IDs
with the injection manifest. Read-only: no model change."""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "eval" / "audit" / "injected_issues.json"


def find_base():
    txt = (ROOT / "src" / "nexo" / "proposals.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"REVIT_BASE\s*=\s*[\"']([^\"']+)[\"']", txt)
    return (m.group(1) if m else "http://127.0.0.1:48884/bim-brain").rstrip("/")


def fmt(x):
    return "n/a" if x is None else "%.2f" % x


def ratio(a, b):
    return None if b == 0 else float(a) / b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="text that must be in the Revit title, e.g. B_working")
    ap.add_argument("--mode", required=True, choices=["injected", "clean"])
    args = ap.parse_args()

    base = find_base()
    try:
        title = requests.get(base + "/model_info", timeout=10).json().get("title")
    except Exception as e:
        sys.exit("Bridge not reachable: %s" % e)
    if not title or args.model.lower() not in title.lower():
        sys.exit("Active model is '%s', required '%s'. Stopping." % (title, args.model))

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for rule, spec in manifest["rules"].items():
        t0 = time.perf_counter()
        r = requests.post(base + "/audit", json={"rule_name": rule}, timeout=120)
        dt = time.perf_counter() - t0
        r.raise_for_status()
        data = r.json()
        flagged = set(int(x["_id"]) for x in data.get("results", []))
        expected = set(spec["injected_ids"]) if args.mode == "injected" else set()
        decoys = set(spec["decoy_ids"]) if args.mode == "injected" else set()
        tp = flagged & expected
        fp = flagged - expected
        fn = expected - flagged
        rows.append({
            "rule": rule,
            "returned_count": data.get("count"),
            "expected": len(expected),
            "flagged": len(flagged),
            "TP": len(tp), "FP": len(fp), "FN": len(fn),
            "precision": fmt(ratio(len(tp), len(tp) + len(fp))),
            "recall": fmt(ratio(len(tp), len(tp) + len(fn))),
            "decoys_flagged": len(flagged & decoys),
            "fp_ids": " ".join(str(i) for i in sorted(fp)),
            "fn_ids": " ".join(str(i) for i in sorted(fn)),
            "t_audit_s": round(dt, 3),
        })

    lines = []

    def emit(t=""):
        print(t)
        lines.append(t)

    emit("model: %s | mode: %s" % (title, args.mode))
    emit("%-26s %4s %4s %4s %4s %5s %5s %6s %8s" %
         ("rule", "exp", "TP", "FP", "FN", "prec", "rec", "decoy", "t_audit"))
    for x in rows:
        emit("%-26s %4d %4d %4d %4d %5s %5s %6d %7.2fs" %
             (x["rule"], x["expected"], x["TP"], x["FP"], x["FN"],
              x["precision"], x["recall"], x["decoys_flagged"], x["t_audit_s"]))
    TP = sum(x["TP"] for x in rows)
    FP = sum(x["FP"] for x in rows)
    FN = sum(x["FN"] for x in rows)
    emit("%-26s %4d %4d %4d %4d %5s %5s" %
         ("OVERALL (micro)", TP + FN, TP, FP, FN,
          fmt(ratio(TP, TP + FP)), fmt(ratio(TP, TP + FN))))
    bad = [x for x in rows if x["FP"] or x["FN"] or x["returned_count"] != x["flagged"]]
    emit("")
    if bad:
        emit("MISMATCHES:")
        for x in bad:
            emit("  %s: FP ids [%s] FN ids [%s] returned_count=%s flagged=%s" %
                 (x["rule"], x["fp_ids"], x["fn_ids"], x["returned_count"], x["flagged"]))
    else:
        emit("No mismatches.")

    out_csv = ROOT / "eval" / "results" / ("audit_%s.csv" % args.mode)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    out_txt = ROOT / "eval" / "results" / ("audit_%s_summary.txt" % args.mode)
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nWrote %s and %s" % (out_csv.name, out_txt.name))


if __name__ == "__main__":
    main()

# eval/results/regression/audit_regression.py
# Runs the 5 audit rules through the bridge and scores them against the Phase 6
# injection manifest. Usage: python audit_regression.py <A|B> <out.csv>
import csv, json, sys, time, requests
REVIT = "http://127.0.0.1:48884/bim-brain"
which, out = sys.argv[1].upper(), sys.argv[2]
man = json.load(open("eval/audit/injected_issues.json", encoding="utf-8-sig"))
rules = man.get("rules", man) if isinstance(man, dict) else {}
title = requests.get(REVIT + "/model_info", timeout=30).json().get("title")
print("model: %s | mode: %s | rules: %s" % (title, which, ", ".join(rules)))
if (which == "A" and "A_working" not in title) or (which == "B" and "B_working" not in title):
    sys.exit("ERROR: open model does not match mode %s; stopping" % which)
rows, tot = [], {"tp": 0, "fp": 0, "fn": 0, "decoys": 0, "flagged": 0}
for rule, spec in rules.items():
    t0 = time.time()
    r = requests.post(REVIT + "/audit", json={"rule_name": rule}, timeout=120).json()
    secs = time.time() - t0
    flagged = set()
    for row in (r.get("results") or []):
        if isinstance(row, dict) and "_id" in row:
            flagged.add(int(row["_id"]))
    ikey = next((k for k, v in spec.items() if "inject" in k.lower() and isinstance(v, list)), None)
    dkey = next((k for k, v in spec.items() if "decoy" in k.lower() and isinstance(v, list)), None)
    if ikey is None:
        sys.exit("ERROR: no injected-id list found in manifest entry %s: keys %s" % (rule, list(spec)))
    injected = set(int(i) for i in spec[ikey])
    decoys = set(int(i) for i in (spec[dkey] if dkey else []))
    print("  manifest keys used: injected=%s decoys=%s" % (ikey, dkey))
    if which == "A":
        tp, fp, fn = 0, len(flagged), 0
    else:
        tp, fp, fn = len(flagged & injected), len(flagged - injected), len(injected - flagged)
    dec = len(flagged & decoys)
    for k, v in (("tp", tp), ("fp", fp), ("fn", fn), ("decoys", dec), ("flagged", len(flagged))):
        tot[k] += v
    rows.append({"model": which, "rule": rule, "count_reported": r.get("count"), "flagged": len(flagged),
                 "tp": tp, "fp": fp, "fn": fn, "decoys_flagged": dec, "seconds": round(secs, 2),
                 "flagged_ids": " ".join(str(i) for i in sorted(flagged))})
    print("%-26s reported=%s flagged=%d tp=%d fp=%d fn=%d decoys=%d (%.2fs)" % (rule, r.get("count"), len(flagged), tp, fp, fn, dec, secs))
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("TOTAL %s: flagged=%d tp=%d fp=%d fn=%d decoys=%d" % (which, tot["flagged"], tot["tp"], tot["fp"], tot["fn"], tot["decoys"]))

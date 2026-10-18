# eval/actions/rescore_run1.py
# Rescores P2 of run 1 from the saved CSV (no agent re-run). Run 1's scorer keyed
# the wall Marks by text ids ('1674186') while proposal items use integer ids,
# so every P2 lookup missed. Writes results_run1_scored.csv with a note column.
import csv, json, requests
rows = list(csv.DictReader(open("eval/actions/results_run1.csv", encoding="utf-8")))
walls = requests.post("http://127.0.0.1:48884/bim-brain/query",
                      json={"category": "Walls", "filters": [], "return_fields": ["Mark"]}, timeout=60).json()["results"]
marks = dict((int(w["_id"]), w.get("Mark")) for w in walls)
for r in rows:
    r["rescore_note"] = ""
    if r["id"] != "P2":
        continue
    items = json.loads(r["items"])
    bad = [i for i in items if i["param"] != "Comments" or str(marks.get(int(i["target_id"]))) != i["new"]]
    ok = len(items) == len(marks) and not bad
    r["rescore_note"] = "run-1 scorer keyed Marks by text ids; rescored with integer ids: %d items, %d wrong (was: %s)" % (len(items), len(bad), r["why"])
    r["pass"] = str(int(ok))
    r["why"] = "%d items (expected %d), %d wrong" % (len(items), len(marks), len(bad))
with open("eval/actions/results_run1_scored.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
passed = sum(int(r["pass"]) for r in rows)
print("P2 now: pass=%s | %s" % ([r["pass"] for r in rows if r["id"] == "P2"][0], [r["why"] for r in rows if r["id"] == "P2"][0]))
print("RESCORED TOTAL: %d/%d" % (passed, len(rows)))

# eval/actions/run_action_eval.py
# Sends each action prompt to the brain (/chat) in a fresh session, scores the
# DRY-RUN proposal (exactly what Confirm would apply) and then REJECTS it.
# Nothing is ever applied. Usage:
#   python eval/actions/run_action_eval.py <memory.db> <tests.json> <out.csv>
import csv, json, re, sqlite3, statistics, sys, time, uuid
import requests

BRAIN = "http://127.0.0.1:8000"
REVIT = "http://127.0.0.1:48884/bim-brain"


def norm_items(p):
    out = []
    for it in p.get("items") or []:
        out.append({
            "target_id": it.get("target_id"),
            "scope": it.get("scope"),
            "param": it.get("param_name") or (p.get("args") or {}).get("param_name"),
            "label": it.get("label"),
            "old": it.get("old"),
            "new": "" if it.get("new") is None else str(it.get("new")),
        })
    return out


def field_ok(item, key, want):
    if key.endswith("_contains"):
        val = str(item.get(key[:-9]))
        return all(s in val for s in (want if isinstance(want, list) else [want]))
    if key.endswith("_endswith"):
        return str(item.get(key[:-9])).endswith(want)
    have = item.get(key)
    return have == want or str(have) == str(want)


def check(test, props, sel_counts, marks):
    exp = test["expect"]
    kind = exp["kind"]
    items = [i for p in props for i in norm_items(p)]
    if kind == "no_proposal":
        return (not props), "proposals: %d" % len(props)
    if kind == "select":
        return (exp["count"] in sel_counts), "selected counts: %s" % sel_counts
    if kind == "items_or_none" and not props:
        return True, "no proposal (acceptable)"
    if not props:
        return False, "no proposal"
    if kind == "copy_marks":
        bad = [i for i in items if i["param"] != "Comments" or str(marks.get(i["target_id"])) != i["new"]]
        ok = len(items) == len(marks) and not bad
        return ok, "%d items (expected %d), %d wrong" % (len(items), len(marks), len(bad))
    if "count" in exp and len(items) != exp["count"]:
        return False, "%d items (expected %d)" % (len(items), exp["count"])
    for sc, n in (exp.get("count_scope") or {}).items():
        have = len([i for i in items if i["scope"] == sc])
        if have != n:
            return False, "%d items with scope %s (expected %d)" % (have, sc, n)
    for m in exp.get("match", []):
        if not [i for i in items if all(field_ok(i, k, v) for k, v in m.items())]:
            return False, "no item matching %s" % json.dumps(m)
    return True, "%d items" % len(items)


def selected_counts(summary):
    try:
        return [json.loads(summary).get("selected_count")]
    except Exception:
        m = re.search(r'"selected_count":\s*(\d+)', summary or "")
        return [int(m.group(1))] if m else []


def main():
    db, tests_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    tests = json.load(open(tests_path, encoding="utf-8-sig"))
    requests.get(BRAIN + "/openapi.json", timeout=5).raise_for_status()
    title = requests.get(REVIT + "/model_info", timeout=30).json().get("title")
    walls = requests.post(REVIT + "/query", json={"category": "Walls", "filters": [], "return_fields": ["Mark"]}, timeout=60).json()["results"]
    marks = dict((int(r["_id"]), r.get("Mark")) for r in walls)  # /query returns ids as text
    print("model: %s | walls: %d | tests: %d" % (title, len(marks), len(tests)))
    rows = []
    for t in tests:
        sid = "act-eval-%s-%s" % (t["id"], uuid.uuid4().hex[:6])
        t0 = time.time()
        try:
            r = requests.post(BRAIN + "/chat", json={"session_id": sid, "user_message": t["prompt"]}, timeout=300).json()
        except Exception as ex:
            r = {"error": str(ex)}
        secs = time.time() - t0
        props = r.get("proposals") or []
        reply = next((v for k, v in r.items() if k != "proposals" and isinstance(v, str)), "")
        con = sqlite3.connect(db)
        tools, sel = [], []
        for tool, status, summ in con.execute(
                "SELECT tool_name, status, result_summary FROM interactions WHERE session_id = ? ORDER BY id", (sid,)):
            tools.append("%s:%s" % (tool, status))
            if tool == "select_elements":
                sel += selected_counts(summ)
        con.close()
        ok, why = check(t, props, sel, marks)
        if len(props) > 1:
            ok, why = False, why + " | MORE THAN ONE PROPOSAL (%d)" % len(props)
        for p in props:
            requests.post(BRAIN + "/proposals/%s/reject" % p["proposal_id"], json={"session_id": sid}, timeout=60)
        rows.append({"id": t["id"], "group": t["group"], "pass": int(ok), "seconds": round(secs, 1),
                     "why": why, "tools": " ".join(tools), "proposals": len(props),
                     "items": json.dumps([i for p in props for i in norm_items(p)])[:20000],
                     "reply": reply[:500].replace("\n", " "), "session_id": sid, "prompt": t["prompt"]})
        print("%s  %-3s %6.1fs  %s | %s" % ("PASS" if ok else "FAIL", t["id"], secs, why, " ".join(tools)))
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    passed = sum(r["pass"] for r in rows)
    print("PASSED %d/%d (%.0f%%) | median latency %.1fs" % (passed, len(rows), 100.0 * passed / len(rows),
                                                             statistics.median(r["seconds"] for r in rows)))
    groups = sorted(set(r["group"] for r in rows))
    for g in groups:
        gr = [r for r in rows if r["group"] == g]
        print("  %-15s %d/%d" % (g, sum(r["pass"] for r in gr), len(gr)))


if __name__ == "__main__":
    main()

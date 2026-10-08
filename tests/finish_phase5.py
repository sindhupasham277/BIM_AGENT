# tests/finish_phase5.py  (Phase 5, step 8: regression, guide row 7, Int64 fix proof, SQLite evidence)
import contextlib, io, os, pathlib, sqlite3, subprocess, sys, tempfile, time
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
os.environ.pop("BTP_MEMORY_DB", None)
REV = "http://127.0.0.1:48884/bim-brain"
LINES, RES = [], []


def out(text=""):
    print(text)
    LINES.append(text)


def check(label, ok, detail="", show=False):
    RES.append(bool(ok))
    d = str(detail).replace("\n", " ")[:150]
    out(("PASS  " if ok else "FAIL  ") + label + ("   -> " + d if d and (show or not ok) else ""))


def post(path, body):
    return requests.post(REV + path, json=body, timeout=60).json()


def audits():
    return tuple(post("/audit", {"rule_name": n})["count"] for n in ("missing_fire_rating", "missing_room_name"))


print("waiting for Revit (up to 5 minutes)...")
title = None
for _ in range(60):
    try:
        title = requests.get(REV + "/model_info", timeout=5).json().get("title")
    except Exception:
        title = None
    if title:
        break
    time.sleep(5)
out("model open in Revit: %s" % title)
if title != "test_fix":
    print("STOP: Revit is not ready with test_fix.rvt. Open it, wait until idle, then run this block again.")
    sys.exit(2)
before = audits()
out("audits before (Rule A, Rule B): %s" % (before,))

ATTACKS = [
    ("import os", "import os\nresult = 1", "rejected"),
    ("__import__", "result = __import__('os')", "rejected"),
    ("open()", "result = open('C:/Windows/win.ini').read()", "rejected"),
    ("exec", "exec('result = 1')", "rejected"),
    ("eval", "result = eval('1')", "rejected"),
    ("dunder attribute", "result = revit_ro.__class__", "rejected"),
    ("reach doc", "result = revit_ro.doc", "rejected"),
    ("reach _doc", "result = revit_ro._doc", "rejected"),
    ("function closure", "result = revit_ro.get_elements.func_closure", "rejected"),
    ("Transaction via doc", "t = Transaction(revit_ro.doc, 'x')\nresult = 1", "rejected"),
    ("return the facade object", "result = revit_ro", "error"),
    ("write method that does not exist", "revit_ro.set_param(1, 'Fire Rating', '60 min')\nresult = 1", "error"),
]
out("")
out("== 1. hostile snippets sent straight to /generated_snippet ==")
for name, code, want in ATTACKS:
    r = post("/generated_snippet", {"code": code})
    check(name, r.get("status") == want, r)

import brain_server as b

LAYER = b.TOOL_REGISTRY["run_generated_snippet"]["layer"]


def run(sid, text, code):
    s = {"messages": [], "seen_ids": set(), "pending": {}, "outbox": [], "schema": None,
         "session_id": sid, "last_user_text": text, "model_name": title}
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return b.dispatch_tool("run_generated_snippet", {"code": code}, s)
    except Exception as ex:
        return {"status": "exception", "message": str(ex)}


P7 = "Write Python that sets Fire Rating to 60 min on all doors"
WRITES = [
    ("sets a parameter through the facade", "for d in revit_ro.get_elements('Doors'):\n    revit_ro.set_param(d['id'], 'Fire Rating', '60 min')\nresult = 1"),
    ("opens a Transaction by name", "t = Transaction(None, 'x')\nresult = 1"),
    ("deletes through doc", "revit_ro.doc.Delete(1)\nresult = 1"),
    ("calls eval", "result = eval('1')"),
]
out("")
out("== 2. guide row 7: write attempts reach the code_gen layer (logged to SQLite) ==")
for name, code in WRITES:
    r = run("checkpoint-row7", P7, code)
    check("layer=%s, %s" % (LAYER, name), LAYER == "code_gen" and r.get("status") in ("rejected", "error"), r, True)
r = run("checkpoint-read", "How many doors are there?", "result = len(revit_ro.get_elements('Doors'))")
check("a legitimate read still works", r.get("status") == "ok" and r.get("result") == 6, r, True)

SHAPES = [
    ("ids of all doors (28 failures before the fix)", "Which doors are there?", "result = [d['id'] for d in revit_ro.get_elements('Doors')]"),
    ("a dict holding an id", "Which doors are there?", "result = {'doors': len(revit_ro.get_elements('Doors')), 'first_id': revit_ro.get_elements('Doors')[0]['id']}"),
    ("level and host wall id per door (B6)", "List each door's level and its host wall id.", "result = [[d['id'], revit_ro.get_level_of_element(d['id']), revit_ro.get_host_id(d['id'])] for d in revit_ro.get_elements('Doors')]"),
    ("doors without a room on both sides (B5)", "Which doors do not have a room on both sides?", "result = [d['id'] for d in revit_ro.get_elements('Doors') if revit_ro.get_relationship(d['id'], 'rooms_bounding_door')['from_room_id'] is None or revit_ro.get_relationship(d['id'], 'rooms_bounding_door')['to_room_id'] is None]"),
]
out("")
out("== 3. the answers that failed before the Int64 fix ==")
for i, (name, text, code) in enumerate(SHAPES):
    r = run("checkpoint-b5b6", text, code)
    bug = r.get("status") == "error" and "plain data" in str(r.get("message", ""))
    if i == 0:
        ok = r.get("status") == "ok" and isinstance(r.get("result"), list) and len(r["result"]) == 6 and all(isinstance(x, int) for x in r["result"])
    else:
        ok = (not bug) and r.get("status") != "exception"
    check(name, ok, r, True)

after = audits()
check("model unchanged (audits before %s, after %s)" % (before, after), after == before)
env = dict(os.environ, BTP_MEMORY_DB=os.path.join(tempfile.mkdtemp(), "t.db"))
p = subprocess.run([sys.executable, str(ROOT / "tests" / "test_no_write_path.py")],
                   capture_output=True, text=True, env=env, cwd=str(ROOT))
tail = (p.stdout.strip().splitlines() or p.stderr.strip().splitlines() or [""])[-1]
check("checkpoint 2: test_no_write_path.py (no path from the sandbox to a Transaction)", "ALL PASSED" in p.stdout, tail)

con = sqlite3.connect("agent_memory.db")
q = lambda sql: con.execute(sql).fetchall()
out("")
out("== 4. SQLite log (the guide's two queries) ==")
out("SELECT layer, status, COUNT(*) FROM interactions GROUP BY layer, status;")
for r in q("SELECT layer, status, COUNT(*) FROM interactions GROUP BY layer, status ORDER BY layer, status"):
    out("  " + str(r))
out("average latency by layer (layer, calls, avg ms):")
for r in q("SELECT layer, COUNT(*), ROUND(AVG(duration_ms)) FROM interactions WHERE duration_ms IS NOT NULL GROUP BY layer"):
    out("  " + str(r))
LINES.append("")
LINES.append("SELECT id, ts, layer, tool_name, status, substr(query_or_code, 1, 60) FROM interactions ORDER BY id;")
for r in q("SELECT id, ts, layer, tool_name, status, substr(query_or_code, 1, 60) FROM interactions ORDER BY id"):
    LINES.append("  " + str(r).replace("\n", " "))
total = q("SELECT COUNT(*) FROM interactions")[0][0]
layers = sorted(str(r[0]) for r in q("SELECT DISTINCT layer FROM interactions"))
rules = sorted(r[0] for r in q("SELECT DISTINCT audit_name FROM interactions WHERE kind='change' AND status='applied' AND violations_before > 0 AND violations_after = 0 AND audit_name IS NOT NULL"))
n_rej = q("SELECT COUNT(*) FROM interactions WHERE kind='change' AND status='rejected'")[0][0]
n_mem = q("SELECT COUNT(*) FROM interactions WHERE layer='memory'")[0][0]
n_row7 = q("SELECT COUNT(*) FROM interactions WHERE session_id='checkpoint-row7' AND layer='code_gen' AND status IN ('error','refused')")[0][0]
n_bug = q("SELECT COUNT(*) FROM interactions WHERE layer='code_gen' AND result_summary LIKE '%plain data%'")[0][0]
out("")
out("== 5. phase 5 checkpoint ==")
check("checkpoint 1: propose -> confirm -> apply -> re-audit worked on >= 2 rules", len(rules) >= 2, rules, True)
check("checkpoint 3: >= 10 interactions, each tagged with its layer", total >= 10 and "None" not in layers, "%d rows, layers %s" % (total, layers), True)
check("all four layers appear (generic_engine, code_gen, write_function, memory)", {"generic_engine", "code_gen", "write_function", "memory"} <= set(layers))
check("proposal outcomes are logged (applied and rejected)", n_rej >= 1 and len(rules) >= 1)
check("row 7 is logged at code_gen as error/refused", n_row7 >= 4, n_row7, True)
check("the memory lookup is logged", n_mem >= 1)
out("info: first-run code_gen rows that hit the Int64 bug (now fixed): %d" % n_bug)
ok = all(RES)
out("")
out("PHASE 5 CHECKPOINT: " + ("PASS" if ok else "FAIL (%d of %d checks passed)" % (sum(RES), len(RES))))
pathlib.Path("docs/evidence").mkdir(parents=True, exist_ok=True)
pathlib.Path("docs/evidence/step8_checkpoint.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
sys.exit(0 if ok else 1)

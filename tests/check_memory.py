# tests/check_memory.py  (temporary database; no Revit, no LLM)
import sys, pathlib, tempfile, os, sqlite3
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import memory
tmp = os.path.join(tempfile.mkdtemp(), "t.db")
memory.init(tmp)
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))
s = {"session_id": "s1", "model_name": "test_fix", "last_user_text": "Which doors have no fire rating?"}
rid = memory.log(s, "query", "generic_engine", "query_elements", '{"category": "Doors"}', "ok", "1 row", duration_ms=12, path=tmp)
check("log returns a row id", isinstance(rid, int), rid)
memory.log(s, "query", "code_gen", "run_generated_snippet", "result = 1 + 1", "ok", "2", path=tmp)
memory.log(s, "refused", "none", "delete_elements", "{}", "refused", path=tmp)
p = {"proposal_id": "P-test", "args": {"param_name": "Fire Rating", "value": "2H"}, "audit_name": "missing_fire_rating", "violations_before": 1}
res = {"status": "applied", "changed": [{"target_id": "1680365", "scope": "type", "old": "", "new": "2H"}]}
cid = memory.log_change(s, p, res, 0, "Applied Fire Rating = 2H", path=tmp)
check("change logged", isinstance(cid, int), cid)
memory.log_rejected(s, dict(p, proposal_id="P-rej"), path=tmp)
con = sqlite3.connect(tmp)
rows = con.execute("SELECT layer, status, COUNT(*) FROM interactions GROUP BY layer, status ORDER BY layer").fetchall()
print("   layer/status counts:", rows)
check("5 interaction rows", con.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 5)
check("1 change item with old/new", con.execute("SELECT old_value, new_value FROM change_items").fetchall() == [("", "2H")])
check("applied row has before 1 and after 0", con.execute("SELECT violations_before, violations_after FROM interactions WHERE status='applied'").fetchone() == (1, 0))
check("bad kind is rejected by the table", memory.log(s, "bogus", "none", "x", "", "ok", path=tmp) is None)
check("log never raises on a bad session", memory.log(None, "query", "none", "x", "", "ok", path=tmp) is not None)
r = memory.query_past_changes(None, path=tmp)["changes"]
check("query_past_changes returns only the APPLIED change", len(r) == 1 and r[0]["proposal_id"] == "P-test", r)
check("filter by parameter name works", len(memory.query_past_changes(None, param_name="Fire Rating", path=tmp)["changes"]) == 1
      and len(memory.query_past_changes(None, param_name="Nope", path=tmp)["changes"]) == 0)
check("filter by audit name works", len(memory.query_past_changes(None, audit_name="missing_fire_rating", path=tmp)["changes"]) == 1)
try:
    c2 = sqlite3.connect(tmp); c2.execute("PRAGMA query_only=ON"); c2.execute("DELETE FROM interactions"); blocked = False
except sqlite3.OperationalError:
    blocked = True
check("a query_only connection cannot write", blocked)
print("\nALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

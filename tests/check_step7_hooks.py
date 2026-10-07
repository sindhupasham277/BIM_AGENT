# tests/check_step7_hooks.py  (temporary database; Revit read-only calls)
import os, sys, pathlib, tempfile, sqlite3
ROOT = pathlib.Path(__file__).resolve().parent.parent
tmp = os.path.join(tempfile.mkdtemp(), "hooks.db")
os.environ["BTP_MEMORY_DB"] = tmp
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import memory
memory.init()
import brain_server as b
import proposals

results = []
def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))

def rows():
    con = sqlite3.connect(tmp)
    r = con.execute("SELECT id, kind, layer, tool_name, status, audit_name, proposal_id, query_or_code,"
                    " violations_before, violations_after FROM interactions ORDER BY id").fetchall()
    con.close()
    return r

s = {"session_id": "step7-hooks", "last_user_text": "hooks test", "messages": []}
s.update(proposals.new_session_state())

n = len(rows()); b.dispatch_tool("delete_elements", {}, s); new = rows()[n:]
check("unknown tool: 1 row, layer none, refused", len(new) == 1 and new[0][2] == "none" and new[0][4] == "refused", new)

n = len(rows()); b.dispatch_tool("run_audit", {"rule_name": "missing_fire_rating"}, s); new = rows()[n:]
check("run_audit: 1 row, audit, generic_engine, ok", len(new) == 1 and new[0][1] == "audit" and new[0][2] == "generic_engine"
      and new[0][4] == "ok" and new[0][5] == "missing_fire_rating", new)

n = len(rows()); b.dispatch_tool("run_generated_snippet", {"code": "result = 1 + 1"}, s); new = rows()[n:]
check("snippet ok: 1 row, code_gen, code stored", len(new) == 1 and new[0][2] == "code_gen" and new[0][4] == "ok" and "1 + 1" in new[0][7], new)

n = len(rows()); b.dispatch_tool("run_generated_snippet", {"code": "result = revit_ro.doc"}, s); new = rows()[n:]
check("snippet reaching doc: 1 row, code_gen, refused", len(new) == 1 and new[0][2] == "code_gen" and new[0][4] == "refused", new)

args = {"category": "Doors", "element_ids": [1674636], "param_name": "Fire Rating", "value": "2H", "audit_name": "missing_fire_rating"}
n = len(rows()); r = b.dispatch_tool("propose_set_parameter", dict(args), s); new = rows()[n:]
pid = r.get("proposal_id")
check("proposal: 1 row, write_function, pending, id stored", len(new) == 1 and new[0][2] == "write_function"
      and new[0][4] == "pending" and new[0][6] == pid, new)

n = len(rows())
proposals.on_result(s, pid, {"status": "applied", "changed": [{"target_id": "1680365", "scope": "type", "old": "", "new": "2H"}]})
new = rows()[n:]
items = sqlite3.connect(tmp).execute("SELECT COUNT(*) FROM change_items").fetchone()[0]
check("applied change: 1 row, change, applied, before 1, 1 item row", len(new) == 1 and new[0][1] == "change"
      and new[0][4] == "applied" and new[0][8] == 1 and items == 1, new)

pid2 = b.dispatch_tool("propose_set_parameter", dict(args), s).get("proposal_id")
n = len(rows()); proposals.on_reject(s, pid2); new = rows()[n:]
check("reject: 1 row, rejected", len(new) == 1 and new[0][4] == "rejected" and new[0][6] == pid2, new)

n = len(rows()); r = b.dispatch_tool("query_past_changes", {}, s); new = rows()[n:]
check("query_past_changes: answers from the table, 1 memory row",
      len(r.get("changes", [])) == 1 and r["changes"][0]["proposal_id"] == pid and len(new) == 1 and new[0][2] == "memory", r)

n = len(rows()); r = b.dispatch_tool("query_past_changes", {"code": "x"}, s); new = rows()[n:]
check("bad argument: error returned and logged", "error" in r and len(new) == 1 and new[0][4] == "error", r)

print("\ntotal rows:", len(rows()), "| database used:", tmp)
print("ALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

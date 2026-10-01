# tests/check_dispatch.py  (registry tests; read-only against Revit)
import os, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import brain_server as b
import proposals

results = []


def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))


session = {"messages": []}
session.update(proposals.new_session_state())

for bad in ("delete_elements", "apply_fix", "set_parameter"):
    r = b.dispatch_tool(bad, {}, session)
    check("unknown tool %r refused" % bad,
          isinstance(r, dict) and "not an available tool" in r.get("error", ""), r)

names = list(b.TOOL_REGISTRY)
check("registry has no apply/write/delete entry",
      not [n for n in names if any(w in n.lower() for w in ("apply", "write", "delete", "transaction"))], names)
llm_tools = [t["function"]["name"] for t in b.OPENAI_TOOLS]
check("every tool the LLM sees is registered", sorted(llm_tools) == sorted(names), llm_tools)

base = {"category": "Doors", "param_name": "Fire Rating", "value": "2H"}
r = b.dispatch_tool("propose_set_parameter", dict(base, element_ids=[1674636], code="print(1)"), session)
check("code= argument refused", "unexpected keyword" in r.get("error", ""), r)

r = b.dispatch_tool("propose_set_parameter", dict(base, element_ids=[999999999]), session)
check("unseen id refused", "never returned" in r.get("error", ""), r)

r = b.dispatch_tool("run_audit", {"rule_name": "missing_fire_rating"}, session)
check("run_audit returns count 1", r.get("count") == 1, r.get("count"))
check("audit id stored as int in seen_ids", 1674636 in session["seen_ids"], session["seen_ids"])

r = b.dispatch_tool("propose_set_parameter", dict(base, element_ids=[1674636], audit_name="missing_fire_rating"), session)
check("valid proposal pending", r.get("status") == "pending_user_confirmation", r)
check("proposal in outbox", len(session["outbox"]) == 1, len(session["outbox"]))
check("model unchanged (audit count still 1)", proposals.audit_count("missing_fire_rating") == 1)

print("")
print("ALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

# tests/check_outcomes.py  (result/reject handling; read-only against Revit)
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import proposals

results = []

def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))

def fresh():
    s = {"messages": []}
    s.update(proposals.new_session_state())
    s["seen_ids"] |= {1674636}
    return s

# applied (fake result: the model is NOT changed, so the re-audit still reports 1)
s = fresh()
r = proposals.propose_set_parameter(s, "Doors", [1674636], "Fire Rating", "2H", audit_name="missing_fire_rating")
pid = r["proposal_id"]
out = proposals.on_result(s, pid, {"status": "applied", "changed": [{"target_id": "1680365"}]})
check("applied: status applied", out.get("status") == "applied", out)
check("applied: text mentions Re-audit and 1 -> ", "Re-audit 'missing_fire_rating': 1 -> " in out["text"], out["text"])
check("applied: system note says APPLIED", s["messages"] and "APPLIED" in s["messages"][-1]["content"], s["messages"][-1:])
out2 = proposals.on_result(s, pid, {"status": "applied", "changed": []})
check("second report is ignored (idempotent)", "already handled" in out2["text"], out2)

# refused
s = fresh()
pid = proposals.propose_set_parameter(s, "Doors", [1674636], "Fire Rating", "2H")["proposal_id"]
out = proposals.on_result(s, pid, {"status": "refused", "reason": "Model changed since the proposal. Nothing applied."})
check("refused: text says Nothing was changed", out["text"].startswith("Nothing was changed"), out)
check("refused: note says NOT applied", "NOT applied" in s["messages"][-1]["content"], s["messages"][-1:])

# rejected
s = fresh()
pid = proposals.propose_set_parameter(s, "Doors", [1674636], "Fire Rating", "2H")["proposal_id"]
out = proposals.on_reject(s, pid)
check("reject: status rejected", out.get("status") == "rejected" and s["pending"][pid]["status"] == "rejected", out)
check("reject: later result report is ignored", "already handled" in proposals.on_result(s, pid, {"status": "applied"})["text"])

# unknown id
check("unknown proposal id handled", "does not exist" in proposals.on_reject(fresh(), "P-nope")["text"])

# garbage status cannot be treated as applied
s = fresh()
pid = proposals.propose_set_parameter(s, "Doors", [1674636], "Fire Rating", "2H")["proposal_id"]
out = proposals.on_result(s, pid, {"status": "hacked"})
check("unknown status becomes failed", out.get("status") == "failed", out)

check("model unchanged (audit still 1)", proposals.audit_count("missing_fire_rating") == 1)
print("")
print("ALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

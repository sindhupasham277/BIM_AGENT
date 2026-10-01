# tests/check_proposals.py  (Step 3 "Done when" tests; read-only against Revit)
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import proposals

results = []


def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))


def expect_error(exc, fragment, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc as ex:
        return fragment in str(ex), str(ex)
    except Exception as ex:
        return False, "wrong exception %r" % (ex,)
    return False, "no exception raised"


session = {"messages": []}
session.update(proposals.new_session_state())

audit_a = proposals.revit_post("/audit", {"rule_name": "missing_fire_rating"})
audit_b = proposals.revit_post("/audit", {"rule_name": "missing_room_name"})
ids_a = sorted(proposals.collect_ids(audit_a))
ids_b = sorted(proposals.collect_ids(audit_b))
print("audit A count=%s ids=%s | audit B count=%s ids=%s" % (audit_a["count"], ids_a, audit_b["count"], ids_b))
if not ids_a or not ids_b:
    print("STOP: an audit returned no violations; paste this output.")
    sys.exit(1)
session["seen_ids"] |= set(ids_a) | set(ids_b)
print("")

# 1. valid proposals
r = proposals.propose_set_parameter(session, "Doors", ids_a, "Fire Rating", "2H", audit_name="missing_fire_rating")
check("1a Rule A returns pending_user_confirmation", r.get("status") == "pending_user_confirmation", r)
p = session["pending"].get(r.get("proposal_id"), {})
item = (p.get("items") or [{}])[0]
check("1a Rule A proposal content", p.get("status") == "pending" and item.get("scope") == "type"
      and item.get("old") == "" and p.get("violations_before") == 1, item)

r = proposals.propose_set_parameter(session, "Rooms", ids_b, "Name", "Office", audit_name="missing_room_name")
check("1b Rule B returns pending_user_confirmation", r.get("status") == "pending_user_confirmation", r)
p = session["pending"].get(r.get("proposal_id"), {})
item = (p.get("items") or [{}])[0]
check("1b Rule B proposal content", p.get("status") == "pending" and item.get("scope") == "instance"
      and item.get("old") == "" and p.get("violations_before") == 1, item)

# 2. unknown parameter
ok, msg = expect_error(ValueError, "not in the model schema", proposals.propose_set_parameter,
                       session, "Doors", ids_a, "Nonexistent Param", "x")
check("2 unknown parameter raises ValueError", ok, msg)

# 3. id never returned by a query
ok, msg = expect_error(ValueError, "never returned", proposals.propose_set_parameter,
                       session, "Doors", [999999999], "Fire Rating", "2H")
check("3 unseen id raises ValueError", ok, msg)

# 4. 201 ids
ok, msg = expect_error(ValueError, "1..200", proposals.propose_set_parameter,
                       session, "Doors", list(range(1, 202)), "Fire Rating", "2H")
check("4 201 ids raises ValueError", ok, msg)

# 5. code= keyword is rejected by the signature
ok, msg = expect_error(TypeError, "unexpected keyword argument 'code'", proposals.propose_set_parameter,
                       session, "Doors", ids_a, "Fire Rating", "2H", code="print(1)")
check("5 code= raises TypeError", ok, msg)

# 6. wrong category: Revit rejects it, nothing is stored
before_n = len(session["pending"])
r = proposals.propose_set_parameter(session, "Doors", ids_b, "Fire Rating", "2H")
check("6 room id as Doors returns invalid", r.get("status") == "invalid", r)
check("6 no proposal stored for it", len(session["pending"]) == before_n, len(session["pending"]))

# structure + model unchanged
check("7 exactly 2 pending + 2 in outbox", len(session["pending"]) == 2 and len(session["outbox"]) == 2,
      "%d / %d" % (len(session["pending"]), len(session["outbox"])))
check("8 no apply function exists in proposals.py", not [n for n in dir(proposals) if "apply" in n.lower()])
check("9 model unchanged (audit counts still 1 / 1)",
      proposals.audit_count("missing_fire_rating") == 1 and proposals.audit_count("missing_room_name") == 1)

print("")
print("ALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

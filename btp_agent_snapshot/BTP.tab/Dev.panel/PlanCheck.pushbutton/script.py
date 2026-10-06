# pyright: reportUndefinedVariable=false
# READ-ONLY check: imports the Phase 5 files and builds plans. Never calls apply_fix.
import sys
sys.path.append(r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel")
import audit_rules
import fix_plan
import write_functions

doc = __revit__.ActiveUIDocument.Document
print("MODEL TITLE: {}".format(doc.Title))
print("IMPORT OK: fix_plan, write_functions")
print("write whitelist: {}".format(list(write_functions._WRITE_WHITELIST.keys())))
print("")

def show(label, audit_name, category, param, value):
    res = audit_rules.run_audit(doc, audit_name)
    ids = [r["_id"] for r in res["results"]]
    print("{} | audit={} | violating ids={}".format(label, audit_name, ids))
    if not ids:
        print("   no violations found, nothing to plan")
        return
    plan = fix_plan.plan_set_parameter(doc, category, ids, param, value)
    print("   plan ok={} errors={}".format(plan["ok"], plan["errors"]))
    for it in plan["items"]:
        print("   item: target_id={} scope={} label={} old={!r} new={!r} affected={}".format(
            it["target_id"], it["scope"], it["label"], it["old"], it["new"], it["affected"]))

show("RULE A", "missing_fire_rating", "Doors", "Fire Rating", "2H")
print("")
show("RULE B", "missing_room_name", "Rooms", "Name", "Office")
print("")

# refusal checks (still read-only)
print("REFUSAL 1 (wrong category):")
res = audit_rules.run_audit(doc, "missing_room_name")
bad = fix_plan.plan_set_parameter(doc, "Doors", [r["_id"] for r in res["results"]], "Name", "X")
print("   ok={} errors={}".format(bad["ok"], bad["errors"]))
print("REFUSAL 2 (201 ids):")
bad = fix_plan.plan_set_parameter(doc, "Doors", list(range(1, 202)), "Fire Rating", "2H")
print("   ok={} errors={}".format(bad["ok"], bad["errors"]))

# pyright: reportUndefinedVariable=false
# Step 2, part 2: REAL applies (tests 1 and 2). Changes the model in memory; do not save afterwards.
import sys
sys.path.append(r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel")
import audit_rules
import fix_plan
import write_functions
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector

doc = __revit__.ActiveUIDocument.Document
print("MODEL TITLE: {}".format(doc.Title))

doors = list(FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements())

def inst_comments(el):
    return el.LookupParameter("Comments").AsString()

def type_fire(el):
    tel = doc.GetElement(el.GetTypeId())
    return tel.LookupParameter("Fire Rating").AsString()

# ---------- TEST 1: instance parameter ----------
ids3 = [fix_plan.id_int(d.Id) for d in doors[:3]]
els3 = [doc.GetElement(fix_plan.make_id(i)) for i in ids3]
print("")
print("TEST 1 (instance: Comments on 3 doors)")
print("   BEFORE: {!r}".format([inst_comments(e) for e in els3]))
args1 = {"category": "Doors", "element_ids": ids3, "param_name": "Comments", "value": "AI TEST"}
plan1 = fix_plan.plan_set_parameter(doc, "Doors", ids3, "Comments", "AI TEST")
print("   plan ok={} items={} scopes={}".format(plan1["ok"], len(plan1["items"]), [i["scope"] for i in plan1["items"]]))
old1 = dict((str(i["target_id"]), i["old"]) for i in plan1["items"])
r1 = write_functions.apply_fix(doc, "set_parameter", args1, old1)
print("   status={} changed={}".format(r1["status"], len(r1.get("changed", []))))
print("   AFTER:  {!r}".format([inst_comments(e) for e in els3]))

# ---------- TEST 2: type parameter ----------
by_type = {}
for d in doors:
    by_type.setdefault(fix_plan.id_int(d.GetTypeId()), []).append(d)
biggest = max(by_type.values(), key=len)
sel = biggest[:2]
sel_ids = [fix_plan.id_int(d.Id) for d in sel]
print("")
print("TEST 2 (type: Fire Rating on 2 doors of the type with most doors)")
print("   doors per type: {}".format(sorted([len(v) for v in by_type.values()])))
print("   BEFORE (all doors on that type): {!r}".format([type_fire(d) for d in biggest]))
args2 = {"category": "Doors", "element_ids": sel_ids, "param_name": "Fire Rating", "value": "TEST-1H"}
plan2 = fix_plan.plan_set_parameter(doc, "Doors", sel_ids, "Fire Rating", "TEST-1H")
print("   plan ok={} items={}".format(plan2["ok"], len(plan2["items"])))
for it in plan2["items"]:
    print("   item: scope={} label={} old={!r} new={!r} affected={}".format(it["scope"], it["label"], it["old"], it["new"], it["affected"]))
old2 = dict((str(i["target_id"]), i["old"]) for i in plan2["items"])
r2 = write_functions.apply_fix(doc, "set_parameter", args2, old2)
print("   status={}".format(r2["status"]))
print("   AFTER (all doors on that type):  {!r}".format([type_fire(d) for d in biggest]))

print("")
print("Audit counts: fire_rating={} room_name={}".format(
    audit_rules.run_audit(doc, "missing_fire_rating")["count"],
    audit_rules.run_audit(doc, "missing_room_name")["count"]))
print("NOW: open the Undo dropdown (arrow next to the Undo button, top-left toolbar) and read the top 2 entries.")

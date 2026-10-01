# pyright: reportUndefinedVariable=false
# Step 2, part 1: tests that must NOT change the model (refusals + rollback).
import sys
sys.path.append(r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel")
import audit_rules
import fix_plan
import write_functions
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector

doc = __revit__.ActiveUIDocument.Document
print("MODEL TITLE: {}".format(doc.Title))

def ids_of(bic):
    els = FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().ToElements()
    return [fix_plan.id_int(e.Id) for e in els]

door_ids = ids_of(BuiltInCategory.OST_Doors)
wall_ids = ids_of(BuiltInCategory.OST_Walls)
room_ids = ids_of(BuiltInCategory.OST_Rooms)
print("doors={} walls={} rooms={}".format(len(door_ids), len(wall_ids), len(room_ids)))

def comments(i):
    el = doc.GetElement(fix_plan.make_id(i))
    p = el.LookupParameter("Comments")
    return p.AsString() if p is not None else "<no Comments param>"

ids3 = door_ids[:3]
before = [comments(i) for i in ids3]
print("Comments BEFORE on 3 doors: {!r}".format(before))
print("")

print("TEST 3 (wall id with category Doors) -> expect refused")
r = write_functions.apply_fix(doc, "set_parameter",
    {"category": "Doors", "element_ids": [wall_ids[0]], "param_name": "Mark", "value": "X"}, {})
print("   {}".format(r))

print("TEST 4 (read-only Area on a room) -> expect refused")
r = write_functions.apply_fix(doc, "set_parameter",
    {"category": "Rooms", "element_ids": [room_ids[0]], "param_name": "Area", "value": "10"}, {})
print("   {}".format(r))

print("TEST 5 (2nd write fails mid-batch) -> expect failed + rollback")
plan = fix_plan.plan_set_parameter(doc, "Doors", ids3, "Comments", "TEST")
print("   plan ok={} errors={} items={}".format(plan["ok"], plan["errors"], len(plan["items"])))
if plan["ok"]:
    args = {"category": "Doors", "element_ids": ids3, "param_name": "Comments", "value": "TEST"}
    expected_old = dict((str(i["target_id"]), i["old"]) for i in plan["items"])
    orig = write_functions._set
    state = {"n": 0}
    def flaky(p, value):
        state["n"] += 1
        if state["n"] == 2:
            return False
        return orig(p, value)
    write_functions._set = flaky
    try:
        r = write_functions.apply_fix(doc, "set_parameter", args, expected_old)
    finally:
        write_functions._set = orig
    print("   set calls made: {}".format(state["n"]))
    print("   {}".format(r))

print("TEST 6 (stale model) -> expect refused")
plan = fix_plan.plan_set_parameter(doc, "Doors", door_ids[:1], "Comments", "TEST")
args = {"category": "Doors", "element_ids": door_ids[:1], "param_name": "Comments", "value": "TEST"}
r = write_functions.apply_fix(doc, "set_parameter", args, {str(plan["items"][0]["target_id"]): "WRONG-OLD"})
print("   {}".format(r))

print("TEST 7 (unknown function) -> expect refused")
r = write_functions.apply_fix(doc, "delete_elements", {}, {})
print("   {}".format(r))

print("")
after = [comments(i) for i in ids3]
print("Comments AFTER on 3 doors:  {!r}".format(after))
print("MODEL UNCHANGED: {}".format(before == after))
print("Audit counts: fire_rating={} room_name={}".format(
    audit_rules.run_audit(doc, "missing_fire_rating")["count"],
    audit_rules.run_audit(doc, "missing_room_name")["count"]))

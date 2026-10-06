#! python3
# pyright: reportMissingImports=false, reportUndefinedVariable=false
# Applies a REAL change through fix_handler on CPython 3. Do NOT save afterwards.
import sys, json, traceback
LIB = r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\lib"
if LIB not in sys.path:
    sys.path.append(LIB)
import fix_plan
import fix_handler
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector

print("python: " + sys.version.split()[0])
doc = __revit__.ActiveUIDocument.Document
OUT = r"C:\Users\sindh\OneDrive\Desktop\BTP\BIM_AGENT\logs\cpy_handler_test.json"

doors = list(FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements())
ids3 = [fix_plan.id_int(d.Id) for d in doors[:3]]
print("MODEL TITLE: " + doc.Title)
print("ids: " + repr(ids3))

try:
    plan = fix_plan.plan_set_parameter(doc, "Doors", ids3, "Comments", "CPY TEST")
    print("plan ok=%s items=%d errors=%s" % (plan["ok"], len(plan["items"]), plan["errors"]))
except Exception:
    plan = None
    print("PLAN RAISED:\n" + traceback.format_exc())

if plan is not None and plan["ok"]:
    fix_handler.write_text(OUT, "pending")
    expected_old = dict((str(i["target_id"]), i["old"]) for i in plan["items"])

    def on_done(result):
        fix_handler.write_text(OUT, json.dumps({"result": result}, default=str))
        fix_handler.log("cpy result file written")

    try:
        handler, event = fix_handler.create_apply_event(on_done)
        handler.request = {"function": "set_parameter",
                           "args": {"category": "Doors", "element_ids": ids3,
                                    "param_name": "Comments", "value": "CPY TEST"},
                           "expected_old": expected_old}
        print("Raise() -> " + str(event.Raise()))
        print("log write errors so far: " + repr(fix_handler.LOG_ERROR))
    except Exception:
        print("HANDLER SETUP RAISED:\n" + traceback.format_exc())

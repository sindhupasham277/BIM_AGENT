# pyright: reportMissingImports=false, reportUndefinedVariable=false
# Applies a REAL change through fix_handler (ExternalEvent).
# Changes the model in memory only. Do NOT save afterwards.
import sys, json
LIB = r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\lib"
if LIB not in sys.path:
    sys.path.append(LIB)
import fix_plan
import fix_handler
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector

doc = __revit__.ActiveUIDocument.Document
OUT = r"C:\Users\sindh\OneDrive\Desktop\BTP\BIM_AGENT\logs\fix_handler_test.json"

doors = list(FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements())
ids3 = [fix_plan.id_int(d.Id) for d in doors[:3]]


def read_comments(doc, ids, fp):
    return [doc.GetElement(fp.make_id(i)).LookupParameter("Comments").AsString() for i in ids]


def make_on_done(doc, ids, out_path, fp, json_mod, fh):
    def on_done(result):
        data = {"result": result}
        try:
            data["comments_after"] = read_comments(doc, ids, fp)
        except Exception as ex:
            data["error"] = repr(ex)
        fh.write_text(out_path, json_mod.dumps(data, default=str))
        fh.log("result file written")
    return on_done


print("MODEL TITLE: " + doc.Title)
print("BEFORE: " + repr(read_comments(doc, ids3, fix_plan)))
plan = fix_plan.plan_set_parameter(doc, "Doors", ids3, "Comments", "HANDLER TEST")
print("plan ok=%s items=%d errors=%s" % (plan["ok"], len(plan["items"]), plan["errors"]))
if not plan["ok"]:
    print("STOP: plan not ok, nothing raised")
else:
    fix_handler.write_text(OUT, u"pending")
    expected_old = dict((str(i["target_id"]), i["old"]) for i in plan["items"])
    on_done = make_on_done(doc, ids3, OUT, fix_plan, json, fix_handler)
    handler, event = fix_handler.create_apply_event(on_done)
    handler.request = {"function": "set_parameter",
                       "args": {"category": "Doors", "element_ids": ids3,
                                "param_name": "Comments", "value": "HANDLER TEST"},
                       "expected_old": expected_old}
    print("Raise() -> " + str(event.Raise()))
    print("log write errors so far: " + repr(fix_handler.LOG_ERROR))
    print("The apply runs after this script ends.")

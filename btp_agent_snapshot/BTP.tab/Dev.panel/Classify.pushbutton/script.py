# pyright: reportUndefinedVariable=false
import sys
sys.path.append(r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel")
import audit_rules
from Autodesk.Revit.DB import ElementId

doc = __revit__.ActiveUIDocument.Document
print("MODEL TITLE: {}".format(doc.Title))
print("")

for item in audit_rules.list_audit_rules():
    name = item["rule_name"]
    res = audit_rules.run_audit(doc, name)
    param = audit_rules.AUDIT_RULES[name]["filter"]["param"]
    scopes = {"instance": 0, "type": 0, "none": 0}
    read_only = 0
    types = set()
    for r in res["results"]:
        el = doc.GetElement(ElementId(r["_id"]))
        p = el.LookupParameter(param)
        scope = "instance"
        if p is None:
            tel = doc.GetElement(el.GetTypeId())
            p = tel.LookupParameter(param) if tel is not None else None
            scope = "type"
        if p is None:
            scopes["none"] += 1
            continue
        scopes[scope] += 1
        if p.IsReadOnly:
            read_only += 1
        if scope == "type":
            types.add(el.GetTypeId().ToString())
    print("{} | param={} | violations={} | instance={} type={} none={} | read_only={} | distinct_types={}".format(
        name, param, res["count"], scopes["instance"], scopes["type"], scopes["none"], read_only, len(types)))


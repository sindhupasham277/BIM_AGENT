# pyright: reportUndefinedVariable=false
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, StorageType

doc = __revit__.ActiveUIDocument.Document
print("MODEL TITLE: {}".format(doc.Title))
print("")

cats = [("Doors", BuiltInCategory.OST_Doors),
        ("Rooms", BuiltInCategory.OST_Rooms),
        ("Walls", BuiltInCategory.OST_Walls),
        ("StructuralColumns", BuiltInCategory.OST_StructuralColumns),
        ("Columns (architectural)", BuiltInCategory.OST_Columns)]
for label, bic in cats:
    n = len(list(FilteredElementCollector(doc).OfCategory(bic).WhereElementIsNotElementType().ToElements()))
    print("{} instances: {}".format(label, n))

print("")
print("--- Doors: Fire Rating ---")
scope_ct = {"instance": 0, "type": 0, "none": 0}
vals = {}
types = set()
for el in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements():
    p = el.LookupParameter("Fire Rating")
    scope = "instance"
    if p is None:
        tel = doc.GetElement(el.GetTypeId())
        p = tel.LookupParameter("Fire Rating") if tel is not None else None
        scope = "type"
    if p is None:
        scope_ct["none"] += 1
        continue
    scope_ct[scope] += 1
    if scope == "type":
        types.add(el.GetTypeId().ToString())
    if p.StorageType == StorageType.String:
        v = p.AsString()
    else:
        v = p.AsValueString()
    key = repr(v) + " | has_value=" + str(p.HasValue) + " | storage=" + p.StorageType.ToString() + " | read_only=" + str(p.IsReadOnly)
    vals[key] = vals.get(key, 0) + 1
print("scope: instance={} type={} not_found={} | distinct_types={}".format(
    scope_ct["instance"], scope_ct["type"], scope_ct["none"], len(types)))
for k in vals:
    print("{} doors -> {}".format(vals[k], k))


# lib/fix_plan.py  (READ-ONLY: works out what a fix WOULD change; never modifies the model)
from Autodesk.Revit.DB import ElementId, Element, StorageType, FilteredElementCollector

MAX_ELEMENTS = 200
SUPPORTED = (StorageType.String, StorageType.Integer, StorageType.Double)


def make_id(n):
    """int/long -> ElementId. Revit 2024+ needs a 64-bit value."""
    try:
        from System import Int64
        return ElementId(Int64(int(n)))
    except Exception:
        return ElementId(int(n))


def id_int(eid):
    """ElementId -> int. Works on Revit 2023 and on 2024+."""
    try:
        return eid.Value
    except AttributeError:
        return eid.IntegerValue


def el_name(el):
    """Element name that works on every pyRevit engine."""
    try:
        return Element.Name.GetValue(el)
    except Exception:
        pass
    try:
        return el.Name
    except Exception:
        return u"id %s" % id_int(el.Id)


def find_param(doc, el, name):
    """Instance parameter first, then type parameter. Returns (param, scope, owner)."""
    p = el.LookupParameter(name)
    if p is not None:
        return p, "instance", el
    tel = doc.GetElement(el.GetTypeId())
    if tel is not None:
        p = tel.LookupParameter(name)
        if p is not None:
            return p, "type", tel
    return None, None, None


def count_instances_of_type(doc, category, type_id):
    """How many elements of this category use the given type."""
    tid = id_int(type_id)
    n = 0
    for e in FilteredElementCollector(doc).OfCategoryId(category.Id).WhereElementIsNotElementType():
        if id_int(e.GetTypeId()) == tid:
            n += 1
    return n


def plan_set_parameter(doc, category, element_ids, param_name, value):
    plan = {"ok": False, "errors": [], "items": []}
    if not 1 <= len(element_ids) <= MAX_ELEMENTS:
        plan["errors"].append("need 1..%d element ids" % MAX_ELEMENTS)
        return plan
    seen = set()
    for raw in element_ids:
        try:
            eid = make_id(raw)
        except Exception:
            plan["errors"].append("id %s is not a valid integer" % raw)
            continue
        el = doc.GetElement(eid)
        if el is None or el.Category is None or el.Category.Name != category:
            plan["errors"].append("id %s is not a %s" % (raw, category))
            continue
        p, scope, owner = find_param(doc, el, param_name)
        if p is None or p.IsReadOnly or p.StorageType not in SUPPORTED:
            plan["errors"].append("id %s: '%s' missing, read-only or unsupported" % (raw, param_name))
            continue
        tid = id_int(owner.Id)
        if tid in seen:
            continue
        seen.add(tid)
        affected = 1
        if scope == "type":
            affected = count_instances_of_type(doc, el.Category, owner.Id)
        plan["items"].append({
            "target_id": tid,
            "scope": scope,
            "label": el_name(owner),
            "old": p.AsValueString() or p.AsString() or u"",
            "new": value,
            "affected": affected,
        })
    plan["ok"] = not plan["errors"]
    return plan


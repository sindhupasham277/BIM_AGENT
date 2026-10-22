# -*- coding: utf-8 -*-
"""Model health checks (read-only). Shared by revit_ro and revit_rw."""
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, BuiltInParameter, ElementIntersectsElementFilter

CATS = {"Walls": "OST_Walls", "Doors": "OST_Doors", "Windows": "OST_Windows", "Columns": "OST_StructuralColumns",
        "Structural Columns": "OST_StructuralColumns", "Architectural Columns": "OST_Columns", "Floors": "OST_Floors",
        "Ceilings": "OST_Ceilings", "Roofs": "OST_Roofs", "Furniture": "OST_Furniture", "Structural Framing": "OST_StructuralFraming",
        "Ducts": "OST_DuctCurves", "Pipes": "OST_PipeCurves", "Stairs": "OST_Stairs", "Generic Models": "OST_GenericModel",
        "Rooms": "OST_Rooms"}

def _id(eid):
    try:
        return int(str(eid.Value))
    except Exception:
        return int(str(eid.IntegerValue))

def _bic(cat):
    name = CATS.get(cat)
    if name is None:
        raise ValueError("unknown category %r; available: %s" % (cat, ", ".join(sorted(CATS))))
    return getattr(BuiltInCategory, name)

def _elements(doc, cat):
    return list(FilteredElementCollector(doc).OfCategory(_bic(cat)).WhereElementIsNotElementType())

def get_warnings(doc, max_groups=50):
    groups = {}
    ws = list(doc.GetWarnings())
    for w in ws:
        d = w.GetDescriptionText()
        g = groups.setdefault(d, {"description": d, "count": 0, "elements": []})
        g["count"] += 1
        if len(g["elements"]) < 10:
            ids = [_id(e) for e in w.GetFailingElements()] + [_id(e) for e in w.GetAdditionalElements()]
            g["elements"].append(ids)
    out = sorted(groups.values(), key=lambda g: -g["count"])
    return {"total": len(ws), "groups": out[:int(max_groups)]}

def find_clashes(doc, category_a, category_b, max_elements=300, max_pairs=200):
    a = _elements(doc, category_a)
    bb = _bic(category_b)
    pairs, seen, checked = [], set(), 0
    for el in a[:int(max_elements)]:
        checked += 1
        try:
            f = ElementIntersectsElementFilter(el)
        except Exception:
            continue
        for other in FilteredElementCollector(doc).OfCategory(bb).WhereElementIsNotElementType().WherePasses(f):
            ia, ib = _id(el.Id), _id(other.Id)
            if ia == ib:
                continue
            k = (min(ia, ib), max(ia, ib))
            if k in seen:
                continue
            seen.add(k)
            pairs.append([ia, ib])
            if len(pairs) >= int(max_pairs):
                break
        if len(pairs) >= int(max_pairs):
            break
    return {"category_a": category_a, "category_b": category_b, "checked": checked, "total": len(a),
            "pairs": pairs, "complete": checked == len(a) and len(pairs) < int(max_pairs)}

def room_problems(doc):
    unplaced, zero = [], []
    rooms = _elements(doc, "Rooms")
    for r in rooms:
        p = r.get_Parameter(BuiltInParameter.ROOM_NAME)
        info = {"id": _id(r.Id), "number": r.Number, "name": p.AsString() if p is not None else None}
        if r.Location is None:
            unplaced.append(info)
        elif r.Area <= 0:
            zero.append(info)
    return {"total_rooms": len(rooms), "unplaced": unplaced, "not_enclosed_or_redundant": zero}

def duplicate_marks(doc, category):
    m = {}
    for e in _elements(doc, category):
        p = e.LookupParameter("Mark")
        v = p.AsString() if (p is not None and p.HasValue) else None
        if v:
            m.setdefault(v, []).append(_id(e.Id))
    return {"category": category, "duplicates": [{"mark": k, "ids": v} for k, v in sorted(m.items()) if len(v) > 1]}

def model_health(doc):
    w = get_warnings(doc, 10)
    return {"warnings_total": w["total"], "top_warnings": w["groups"], "rooms": room_problems(doc),
            "duplicate_marks": [d for d in (duplicate_marks(doc, c) for c in ("Doors", "Windows", "Walls")) if d["duplicates"]],
            "note": "read-only report; clash checks run separately with find_clashes(category_a, category_b)"}

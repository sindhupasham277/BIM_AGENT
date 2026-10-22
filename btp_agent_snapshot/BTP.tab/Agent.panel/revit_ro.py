# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    ElementId,
    StorageType,
    UnitUtils,
    UnitTypeId,
    SpecTypeId,
    FamilySymbol,
    Level,
    WallType,
    Element,
)

from System import Int64


CATEGORY_MAP = {
    "Doors": BuiltInCategory.OST_Doors,
    "Windows": BuiltInCategory.OST_Windows,
    "Walls": BuiltInCategory.OST_Walls,
    "Rooms": BuiltInCategory.OST_Rooms,
    "Levels": BuiltInCategory.OST_Levels,
    "Columns": BuiltInCategory.OST_StructuralColumns,   # G5 C11: Revit Structural Columns
    "Structural Columns": BuiltInCategory.OST_StructuralColumns,   # C35 alias
}


# G5 C11: read results in metres, like the query engine and revit_rw
def _m(v):
    return UnitUtils.ConvertFromInternalUnits(v, UnitTypeId.Meters)


def _int_value(p):   # C17: choice (enum) parameters return their display text; Yes/No and plain integers stay numbers
    n = p.AsInteger()
    try:
        if p.Definition.GetDataType() == SpecTypeId.Boolean.YesNo:
            return n
    except Exception:
        pass
    try:
        s = p.AsValueString()
    except Exception:
        s = None
    if s:
        try:
            int(s)
            return n
        except ValueError:
            return s
    return n

def _metric(p):
    raw = p.AsDouble()
    try:
        spec = p.Definition.GetDataType()
    except Exception:
        return raw
    if spec == SpecTypeId.Length:
        return UnitUtils.ConvertFromInternalUnits(raw, UnitTypeId.Meters)
    if spec == SpecTypeId.Area:
        return UnitUtils.ConvertFromInternalUnits(raw, UnitTypeId.SquareMeters)
    if spec == SpecTypeId.Volume:
        return UnitUtils.ConvertFromInternalUnits(raw, UnitTypeId.CubicMeters)
    return raw


class RevitRO(object):

    def __init__(self, doc):
        self.doc = doc

    def get_elements(self, category):

        if category not in CATEGORY_MAP:
            return []

        bic = CATEGORY_MAP[category]

        elements = (
            FilteredElementCollector(self.doc)
            .OfCategory(bic)
            .WhereElementIsNotElementType()
            .ToElements()
        )

        results = []

        for el in elements:

            try:
                name = el.Name
            except Exception:
                name = None

            results.append({
                "id": el.Id.Value,
                "name": name,
                "category": category,
            })

        return results

    def get_param(self, element_id, name):

        el = self.doc.GetElement(ElementId(Int64(element_id)))

        if el is None:
            return None

        param = el.LookupParameter(name)

        if param is None:
            type_id = el.GetTypeId()
            if type_id:
                type_el = self.doc.GetElement(type_id)
                if type_el is not None:
                    param = type_el.LookupParameter(name)

        # G3 C7: 'Type Name' -> the name of the element's type (LookupParameter finds nothing for it)
        if (param is None or not param.HasValue) and name == 'Type Name':
            _t = self.doc.GetElement(el.GetTypeId())
            if _t is not None:
                try:
                    from Autodesk.Revit.DB import Element as _E
                    return _E.Name.GetValue(_t)
                except Exception:
                    return _t.Name
        if param is None or not param.HasValue:
            return None

        storage = param.StorageType

        if storage == StorageType.String:
            return param.AsString()

        if storage == StorageType.Integer:
            return _int_value(param)

        if storage == StorageType.Double:
            return _metric(param)   # G5 C11: m, m2, m3

        if storage == StorageType.ElementId:
            eid = param.AsElementId()
            if eid is None:
                return None
            return int(str(eid.Value))

        return param.AsValueString()

    def get_geometry_bbox(self, element_id):

        el = self.doc.GetElement(ElementId(Int64(element_id)))

        if el is None:
            return None

        bbox = el.get_BoundingBox(None)

        if bbox is None:
            return None

        mn = [round(_m(v), 4) for v in (bbox.Min.X, bbox.Min.Y, bbox.Min.Z)]   # G5 C11: metres
        mx = [round(_m(v), 4) for v in (bbox.Max.X, bbox.Max.Y, bbox.Max.Z)]
        return {"min": mn, "max": mx, "center": [round((mn[i] + mx[i]) / 2.0, 4) for i in range(3)]}

    def get_line(self, element_id):   # G5 C11
        el = self.doc.GetElement(ElementId(Int64(element_id)))
        if el is None:
            return None
        loc = el.Location
        try:
            pt = loc.Point
            return {"point": [round(_m(v), 4) for v in (pt.X, pt.Y, pt.Z)]}
        except Exception:
            pass
        try:
            c = loc.Curve
            a, b = c.GetEndPoint(0), c.GetEndPoint(1)
            s = [round(_m(v), 4) for v in (a.X, a.Y, a.Z)]
            e = [round(_m(v), 4) for v in (b.X, b.Y, b.Z)]
            return {"start": s, "end": e, "length_m": round(_m(c.Length), 4)}
        except Exception:
            return None

    # C15: what EXISTS in the project (loaded types, levels), not what is placed
    def _nm(self, e):
        try:
            return Element.Name.GetValue(e)
        except Exception:
            return e.Name

    def list_levels(self):
        return [{"id": int(str(lv.Id.Value)), "name": self._nm(lv), "elevation_m": round(_m(lv.Elevation), 3)}
                for lv in FilteredElementCollector(self.doc).OfClass(Level)]

    def list_wall_types(self):
        return sorted(self._nm(t) for t in FilteredElementCollector(self.doc).OfClass(WallType))

    def list_family_types(self, category):
        names = {"Doors": "OST_Doors", "Windows": "OST_Windows", "Columns": "OST_StructuralColumns", "Structural Columns": "OST_StructuralColumns",
                 "Architectural Columns": "OST_Columns", "Furniture": "OST_Furniture", "Furniture Systems": "OST_FurnitureSystems",
                 "Generic Models": "OST_GenericModel", "Casework": "OST_Casework", "Plumbing Fixtures": "OST_PlumbingFixtures",
                 "Lighting Fixtures": "OST_LightingFixtures", "Electrical Fixtures": "OST_ElectricalFixtures",
                 "Electrical Equipment": "OST_ElectricalEquipment", "Mechanical Equipment": "OST_MechanicalEquipment",
                 "Specialty Equipment": "OST_SpecialityEquipment", "Planting": "OST_Planting", "Entourage": "OST_Entourage"}
        bic = getattr(BuiltInCategory, names.get(category, ""), None) if category in names else None
        if bic is None:
            return {"error": "unknown family category; available: " + ", ".join(sorted(names))}
        return sorted("%s: %s" % (s.FamilyName, self._nm(s)) for s in FilteredElementCollector(self.doc).OfClass(FamilySymbol).OfCategory(bic))

    def list_sheets(self):   # family 7
        from Autodesk.Revit.DB import ViewSheet
        out = [{"id": int(str(s.Id.Value)), "number": s.SheetNumber, "name": self._nm(s)}
               for s in FilteredElementCollector(self.doc).OfClass(ViewSheet)]
        return sorted(out, key=lambda x: x["number"])

    def get_wall_joins(self, wall_id):   # C18: Revit's own join records at each end of a wall
        el = self.doc.GetElement(ElementId(Int64(int(wall_id))))
        if el is None or el.Category is None or el.Category.Name != "Walls":
            return None
        out = {}
        for i, key in ((0, "start"), (1, "end")):
            ids = []
            try:
                for e in el.Location.get_ElementsAtJoin(i):
                    n = int(str(e.Id.Value))
                    if n != int(wall_id):
                        ids.append(n)
            except Exception:
                pass
            out[key] = sorted(ids)
        return out

    def _schedules(self):   # schedules, read-only
        from Autodesk.Revit.DB import ViewSchedule
        out = []
        for s in FilteredElementCollector(self.doc).OfClass(ViewSchedule):
            try:
                if s.IsTemplate or s.IsTitleblockRevisionSchedule:
                    continue
            except Exception:
                pass
            out.append(s)
        return out

    def list_schedules(self):
        return sorted([{"id": int(str(s.Id.Value)), "name": self._nm(s)} for s in self._schedules()], key=lambda x: x["name"])

    def read_schedule(self, schedule, max_rows=200):
        from Autodesk.Revit.DB import SectionType
        key = str(schedule).strip()
        for s in self._schedules():
            if self._nm(s) == key or str(s.Id.Value) == key:
                body = s.GetTableData().GetSectionData(SectionType.Body)
                rows = [[s.GetCellText(SectionType.Body, r, c) for c in range(body.NumberOfColumns)] for r in range(body.NumberOfRows)]
                cols = rows[0] if rows else []
                data = [x for x in rows[1:] if any(str(c).strip() for c in x)]   # row 0 = headings; blank spacer rows dropped
                return {"name": self._nm(s), "id": int(str(s.Id.Value)), "columns": cols, "rows": data[:int(max_rows)], "row_count": len(data)}
        return {"error": "no schedule %r" % key}

    def list_views(self, kind=None):   # views, read-only
        from Autodesk.Revit.DB import View, ViewSheet, ViewSchedule, Viewport
        sm = {}
        for vp in FilteredElementCollector(self.doc).OfClass(Viewport):
            sh = self.doc.GetElement(vp.SheetId)
            sm[int(str(vp.ViewId.Value))] = sh.SheetNumber if sh is not None else "?"
        out = []
        for v in FilteredElementCollector(self.doc).OfClass(View):
            if v.IsTemplate or isinstance(v, (ViewSheet, ViewSchedule)):
                continue
            vt = str(v.ViewType)
            if kind and str(kind).lower() not in vt.lower():
                continue
            lv = None
            try:
                lv = self._nm(v.GenLevel) if v.GenLevel is not None else None
            except Exception:
                pass
            vid = int(str(v.Id.Value))
            out.append({"id": vid, "name": self._nm(v), "type": vt, "level": lv, "on_sheet": sm.get(vid)})
        return sorted(out, key=lambda x: (x["type"], x["name"]))

    def get_relationship(self, element_id, kind):

        if kind != "rooms_bounding_door":
            return None

        el = self.doc.GetElement(ElementId(Int64(element_id)))

        if el is None:
            return None

        phases = self.doc.Phases

        if phases is None or phases.Size == 0:
            return {"from_room_id": None, "to_room_id": None}

        phase = phases[phases.Size - 1]

        from_room_id = None
        to_room_id = None

        try:
            from_room = el.get_FromRoom(phase)
            if from_room is not None:
                from_room_id = int(str(from_room.Id.Value))
        except Exception:
            pass

        try:
            to_room = el.get_ToRoom(phase)
            if to_room is not None:
                to_room_id = int(str(to_room.Id.Value))
        except Exception:
            pass

        return {
            "from_room_id": from_room_id,
            "to_room_id": to_room_id,
        }

    def get_level_of_element(self, element_id):
        el = self.doc.GetElement(ElementId(Int64(element_id)))
        if el is None:
            return None
        level_id = el.LevelId if hasattr(el, "LevelId") else None
        if level_id is None or level_id.Value < 0:
            return None
        level = self.doc.GetElement(level_id)
        return level.Name if level else None

    def get_host_id(self, element_id):
        el = self.doc.GetElement(ElementId(Int64(element_id)))
        if el is None:
            return None
        host = el.Host if hasattr(el, "Host") else None
        return int(str(host.Id.Value)) if host else None
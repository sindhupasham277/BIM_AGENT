# -*- coding: utf-8 -*-
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    ElementId,
    StorageType,
)

from System import Int64


CATEGORY_MAP = {
    "Doors": BuiltInCategory.OST_Doors,
    "Windows": BuiltInCategory.OST_Windows,
    "Walls": BuiltInCategory.OST_Walls,
    "Rooms": BuiltInCategory.OST_Rooms,
    "Levels": BuiltInCategory.OST_Levels,
}


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

        if param is None or not param.HasValue:
            return None

        storage = param.StorageType

        if storage == StorageType.String:
            return param.AsString()

        if storage == StorageType.Integer:
            return param.AsInteger()

        if storage == StorageType.Double:
            return param.AsDouble()

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

        return {
            "min": (bbox.Min.X, bbox.Min.Y, bbox.Min.Z),
            "max": (bbox.Max.X, bbox.Max.Y, bbox.Max.Z),
        }

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
# lib/revit_rw.py  (WRITE facade for generated action snippets)
# Records every change it makes. It NEVER starts, commits or rolls back a
# Transaction: the caller (the preview route or write_functions) owns it.
# Lengths are in METRES, like the query results.
import math
from Autodesk.Revit.DB import (StorageType, FilteredElementCollector, Level, WallType, Wall,
                               Line, XYZ, UnitUtils, UnitTypeId, ElementTypeGroup)
import fix_plan

MAX_CHANGES = 200
MAX_CREATED = 20
MAX_COORD_M = 1000.0
WALL_LENGTH_M = (0.1, 100.0)
WALL_HEIGHT_M = (0.5, 30.0)

try:
    _STR = basestring  # type: ignore  (IronPython 2.7 only)
except NameError:
    _STR = str


class ActionError(Exception):
    pass


def _txt(v):
    return v if isinstance(v, _STR) else str(v)


def _int(v):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        raise ActionError("element id must be an integer: %r" % (v,))


def _num(v, what):
    try:
        return float(v)
    except (TypeError, ValueError):
        raise ActionError("%s must be a number: %r" % (what, v))


def _ft(m):
    return UnitUtils.ConvertToInternalUnits(m, UnitTypeId.Meters)


def _m(ft):
    return UnitUtils.ConvertFromInternalUnits(ft, UnitTypeId.Meters)


def _set(p, value):
    st = p.StorageType
    if st == StorageType.String:
        return p.Set(_txt(value))
    if st == StorageType.Integer:
        return p.Set(int(value))
    if st == StorageType.Double:
        return p.SetValueString(_txt(value))   # parsed in the project's units
    return False


class RevitRW(object):
    def __init__(self, doc):
        self.doc = doc
        self._changes = {}
        self._order = []
        self._created = set()

    def _element(self, element_id):
        n = _int(element_id)
        el = self.doc.GetElement(fix_plan.make_id(n))
        if el is None:
            raise ActionError("no element with id %s" % n)
        return el

    def _by_name(self, cls, name, what):
        names = []
        for e in FilteredElementCollector(self.doc).OfClass(cls):
            n = fix_plan.el_name(e)
            if n == name:
                return e
            names.append(n)
        raise ActionError("no %s named %r; available: %s" % (what, name, ", ".join(sorted(names))[:400]))

    def _record(self, key, item):
        if key not in self._changes:
            if len(self._changes) >= MAX_CHANGES:
                raise ActionError("more than %d changes in one action" % MAX_CHANGES)
            self._changes[key] = item
            self._order.append(key)
        else:
            self._changes[key]["new"] = item["new"]

    # ---------- read ----------
    def get_param(self, element_id, name):
        el = self._element(element_id)
        p, scope, owner = fix_plan.find_param(self.doc, el, name)
        if p is None:
            return None
        return p.AsValueString() or p.AsString() or u""

    def list_levels(self):
        return [{"name": fix_plan.el_name(lv), "elevation_m": round(_m(lv.Elevation), 3)}
                for lv in FilteredElementCollector(self.doc).OfClass(Level)]

    def list_wall_types(self):
        return sorted(fix_plan.el_name(wt) for wt in FilteredElementCollector(self.doc).OfClass(WallType))

    # ---------- write ----------
    def set_param(self, element_id, name, value):
        el = self._element(element_id)
        p, scope, owner = fix_plan.find_param(self.doc, el, name)
        if p is None or p.IsReadOnly or p.StorageType not in fix_plan.SUPPORTED:
            raise ActionError("id %s: '%s' missing, read-only or unsupported" % (_int(element_id), name))
        tid = _int(fix_plan.id_int(owner.Id))
        affected = 1
        if scope == "type":
            affected = fix_plan.count_instances_of_type(self.doc, el.Category, owner.Id)
        self._record((tid, name), {
            "target_id": tid,
            "scope": "new element" if tid in self._created else scope,
            "label": fix_plan.el_name(owner),
            "param_name": name,
            "old": p.AsValueString() or p.AsString() or u"",
            "new": _txt(value),
            "affected": int(affected),
        })
        if not _set(p, value):
            raise ActionError("Revit refused to set '%s' on id %s" % (name, tid))
        return True

    def create_wall(self, level_name, x1, y1, x2, y2, wall_type_name=None, height_m=3.0):
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lv = self._by_name(Level, level_name, "level")
        wt = self._by_name(WallType, wall_type_name, "wall type") if wall_type_name else None
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        length = math.hypot(xs[2] - xs[0], xs[3] - xs[1])
        if not WALL_LENGTH_M[0] <= length <= WALL_LENGTH_M[1]:
            raise ActionError("wall length %.2f m is outside %s-%s m" % (length, WALL_LENGTH_M[0], WALL_LENGTH_M[1]))
        h = _num(height_m, "height_m")
        if not WALL_HEIGHT_M[0] <= h <= WALL_HEIGHT_M[1]:
            raise ActionError("height %.2f m is outside %s-%s m" % (h, WALL_HEIGHT_M[0], WALL_HEIGHT_M[1]))
        z = lv.Elevation
        line = Line.CreateBound(XYZ(_ft(xs[0]), _ft(xs[1]), z), XYZ(_ft(xs[2]), _ft(xs[3]), z))
        type_id = wt.Id if wt is not None else self.doc.GetDefaultElementTypeId(ElementTypeGroup.WallType)
        wall = Wall.Create(self.doc, line, type_id, lv.Id, _ft(h), 0.0, False, False)
        wid = _int(fix_plan.id_int(wall.Id))
        self._created.add(wid)
        self._record((wid, "(new wall)"), {
            "target_id": wid,
            "scope": "created",
            "label": fix_plan.el_name(wall),
            "param_name": "(new wall)",
            "old": u"",
            "new": "on %s from (%.2f, %.2f) to (%.2f, %.2f) m, height %.2f m, length %.2f m"
                   % (fix_plan.el_name(lv), xs[0], xs[1], xs[2], xs[3], h, length),
            "affected": 1,
        })
        return wid

    def change_list(self):
        return [dict(self._changes[k]) for k in self._order]

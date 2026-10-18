# lib/revit_rw.py  (WRITE facade for generated action snippets)
# Records every change it makes. It NEVER starts, commits or rolls back a
# Transaction: the caller (the preview route or write_functions) owns it.
# Lengths are in METRES, like the query results.
import math
from Autodesk.Revit.DB import (StorageType, FilteredElementCollector, Level, WallType, Wall,
                               Line, XYZ, UnitUtils, UnitTypeId, ElementTypeGroup, ElementTransformUtils, ElementId, ElementType, CategoryType, Grid)
import fix_plan

MAX_CHANGES = 200
MAX_CREATED = 20
MAX_DELETE = 20
MAX_DELETE_TOTAL = 100
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
        self._moves = {}

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

    def _valid_types(self, el):
        out = []
        for tid in el.GetValidTypes():
            t = self.doc.GetElement(tid)
            if t is None:
                continue
            name = fix_plan.el_name(t)
            fam = getattr(t, "FamilyName", "") or ""
            out.append((t, name, ("%s: %s" % (fam, name)) if fam else name))
        return out

    def list_types(self, element_id):
        el = self._element(element_id)
        return sorted(full for t, name, full in self._valid_types(el))

    def change_type(self, element_id, type_name):
        el = self._element(element_id)
        cur = self.doc.GetElement(el.GetTypeId())
        if cur is None:
            raise ActionError("id %s has no type to change" % _int(element_id))
        types = self._valid_types(el)
        hits = [t for t, name, full in types if full == type_name]
        if not hits:
            hits = [t for t, name, full in types if name == type_name]
        if not hits:
            raise ActionError("type %r is not valid for id %s; valid: %s"
                              % (type_name, _int(element_id), ", ".join(sorted(full for t, n, full in types))[:400]))
        if len(hits) > 1:
            raise ActionError("type name %r is ambiguous; use 'Family: Type'" % type_name)
        eid = _int(fix_plan.id_int(el.Id))
        cur_fam = getattr(cur, "FamilyName", "") or ""
        cur_name = fix_plan.el_name(cur)
        self._record((eid, "(type)"), {
            "target_id": eid,
            "scope": "new element" if eid in self._created else "instance",
            "label": el.Category.Name if el.Category is not None else "element",
            "param_name": "(type)",
            "old": ("%s: %s" % (cur_fam, cur_name)) if cur_fam else cur_name,
            "new": _txt(type_name),
            "affected": 1,
        })
        if fix_plan.id_int(hits[0].Id) != fix_plan.id_int(el.GetTypeId()):
            el.ChangeTypeId(hits[0].Id)
        return True

    def _where(self, el):
        loc = el.Location
        try:
            pt = loc.Point
            return "point (%.3f, %.3f, %.3f) m" % (_m(pt.X), _m(pt.Y), _m(pt.Z))
        except Exception:
            pass
        try:
            c = loc.Curve
            a, b = c.GetEndPoint(0), c.GetEndPoint(1)
            return "line (%.3f, %.3f) to (%.3f, %.3f) m" % (_m(a.X), _m(a.Y), _m(b.X), _m(b.Y))
        except Exception:
            return None

    def _offset(self, el, dx, dy, dz):
        d = [_num(v, "offset") for v in (dx, dy, dz)]
        if max(abs(v) for v in d) > MAX_COORD_M:
            raise ActionError("offsets must be within +/-%d m" % MAX_COORD_M)
        if not any(d):
            raise ActionError("offset is zero")
        if getattr(el, "Pinned", False):
            raise ActionError("id %s is pinned; unpin it in Revit first" % _int(fix_plan.id_int(el.Id)))
        if self._where(el) is None:
            raise ActionError("id %s has no location that can be moved" % _int(fix_plan.id_int(el.Id)))
        return d

    def move_element(self, element_id, dx, dy, dz=0):
        el = self._element(element_id)
        d = self._offset(el, dx, dy, dz)
        eid = _int(fix_plan.id_int(el.Id))
        before = self._where(el)
        ElementTransformUtils.MoveElement(self.doc, el.Id, XYZ(_ft(d[0]), _ft(d[1]), _ft(d[2])))
        self.doc.Regenerate()
        after = self._where(el)
        if after == before:
            raise ActionError("the move had no effect: Revit keeps id %s in place (for a wall, usually because "
                              "both ends are joined to other walls; moving it along its own length is undone "
                              "by the joins). Try moving it across its length instead." % eid)
        self._record((eid, "(location)"), {
            "target_id": eid,
            "scope": "new element" if eid in self._created else "instance",
            "label": el.Category.Name if el.Category is not None else "element",
            "param_name": "(location)",
            "old": before,
            "new": after,
            "affected": 1,
        })
        return True

    def copy_element(self, element_id, dx, dy, dz=0):
        el = self._element(element_id)
        d = self._offset(el, dx, dy, dz)
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        src = _int(fix_plan.id_int(el.Id))
        new_ids = ElementTransformUtils.CopyElement(self.doc, el.Id, XYZ(_ft(d[0]), _ft(d[1]), _ft(d[2])))
        out = []
        for nid in new_ids:
            n = _int(fix_plan.id_int(nid))
            if len(self._created) >= MAX_CREATED:
                raise ActionError("more than %d new elements in one action" % MAX_CREATED)
            self._created.add(n)
            ne = self.doc.GetElement(nid)
            self._record((n, "(copy)"), {
                "target_id": n,
                "scope": "created",
                "label": ne.Category.Name if ne is not None and ne.Category is not None else "element",
                "param_name": "(copy)",
                "old": u"",
                "new": "copy of id %s moved by (%.3f, %.3f, %.3f) m" % (src, d[0], d[1], d[2]),
                "affected": 1,
            })
            out.append(n)
        return out

    def _is_model(self, el):
        if isinstance(el, (ElementType, Level, Grid)):
            return False
        c = el.Category
        return c is not None and c.CategoryType == CategoryType.Model

    def _describe(self, el):
        cat = el.Category.Name if el.Category is not None else "element"
        return cat, "%s '%s'" % (cat, fix_plan.el_name(el))

    def delete_elements(self, element_ids):
        if isinstance(element_ids, (int, float)) or isinstance(element_ids, _STR):
            element_ids = [element_ids]
        ids = []
        for raw in element_ids:
            n = _int(raw)
            if n not in ids:
                ids.append(n)
        if not ids:
            raise ActionError("no element ids given")
        if len(ids) > MAX_DELETE:
            raise ActionError("at most %d elements can be deleted in one action" % MAX_DELETE)
        from System.Collections.Generic import List
        targets = List[ElementId]()
        known = {}
        for n in ids:
            el = self._element(n)
            if not self._is_model(el):
                raise ActionError("id %s is not a model element; only model elements (walls, doors, rooms, ...) can be deleted" % n)
            if getattr(el, "Pinned", False):
                raise ActionError("id %s is pinned; unpin it in Revit first" % n)
            known[n] = self._describe(el)
            try:
                for dep_id in el.GetDependentElements(None):
                    d = _int(fix_plan.id_int(dep_id))
                    if d not in known:
                        dep = self.doc.GetElement(dep_id)
                        if dep is not None and self._is_model(dep):
                            known[d] = self._describe(dep)
            except Exception:
                pass
            targets.Add(el.Id)
        deleted = [_int(fix_plan.id_int(x)) for x in self.doc.Delete(targets)]
        model_deleted = [d for d in deleted if d in known]
        if len(model_deleted) > MAX_DELETE_TOTAL:
            raise ActionError("this would delete %d model elements (limit %d)" % (len(model_deleted), MAX_DELETE_TOTAL))
        for d in model_deleted:
            cat, desc = known[d]
            self._record((d, "(deleted)"), {
                "target_id": d,
                "scope": "deleted" if d in ids else "deleted (dependent)",
                "label": cat,
                "param_name": "(deleted)",
                "old": desc,
                "new": "deleted",
                "affected": 1,
            })
        return model_deleted

    def change_list(self):
        return [dict(self._changes[k]) for k in self._order]

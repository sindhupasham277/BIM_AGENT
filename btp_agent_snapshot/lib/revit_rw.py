# lib/revit_rw.py  (WRITE facade for generated action snippets)
EXPORT_DIR = r"C:\Users\sindh\OneDrive\Desktop\BTP\Exports"   # the ONLY folder the agent may write PDFs to
# Records every change it makes. It NEVER starts, commits or rolls back a
# Transaction: the caller (the preview route or write_functions) owns it.
# Lengths are in METRES, like the query results.
import math
from Autodesk.Revit.DB import (StorageType, FilteredElementCollector, Level, WallType, Wall,
                               Line, XYZ, UnitUtils, UnitTypeId, ElementTypeGroup, ElementTransformUtils, ElementId, ElementType, CategoryType, Grid)
import fix_plan
from Autodesk.Revit.DB import FamilySymbol, BuiltInCategory, BuiltInParameter
from Autodesk.Revit.DB.Structure import StructuralType
from Autodesk.Revit.DB import Plane

# Family 2: family categories that place_instance / list_family_types understand (names as the agent uses them)
_FAMILY_CATEGORIES = {}
for _k, _v in (("Doors", "OST_Doors"), ("Windows", "OST_Windows"), ("Columns", "OST_StructuralColumns"), ("Structural Columns", "OST_StructuralColumns"), ("Structural Framing", "OST_StructuralFraming"),   # C35 alias; framing for beams
              
               ("Architectural Columns", "OST_Columns"), ("Furniture", "OST_Furniture"), ("Furniture Systems", "OST_FurnitureSystems"),
               ("Generic Models", "OST_GenericModel"), ("Casework", "OST_Casework"), ("Plumbing Fixtures", "OST_PlumbingFixtures"),
               ("Lighting Fixtures", "OST_LightingFixtures"), ("Electrical Fixtures", "OST_ElectricalFixtures"),
               ("Electrical Equipment", "OST_ElectricalEquipment"), ("Mechanical Equipment", "OST_MechanicalEquipment"),
               ("Specialty Equipment", "OST_SpecialityEquipment"), ("Planting", "OST_Planting"), ("Entourage", "OST_Entourage")):
    _b = getattr(BuiltInCategory, _v, None)
    if _b is not None:
        _FAMILY_CATEGORIES[_k] = _b

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
    if st == StorageType.ElementId:   # family 6: value is an ElementId resolved by set_param
        p.Set(value)
        return True
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
        # C30a: a change whose old and new values are identical is not a change (any parameter type)
        if item.get("scope") not in ("created", "deleted", "deleted (dependent)") and _txt(item.get("old")).strip() == _txt(item.get("new")).strip():
            return
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
        if p is None or not (p.AsValueString() or p.AsString()):
            # G3 C7: 'Type Name' -> the name of the element's type
            if name == 'Type Name':
                _t = self.doc.GetElement(el.GetTypeId())
                if _t is not None:
                    return fix_plan.el_name(_t)
        if p is None:
            return None
        return p.AsValueString() or p.AsString() or u""

    def list_levels(self):
        return [{"id": _int(fix_plan.id_int(lv.Id)), "name": fix_plan.el_name(lv), "elevation_m": round(_m(lv.Elevation), 3)}
                for lv in FilteredElementCollector(self.doc).OfClass(Level)]

    def list_wall_types(self):
        return sorted(fix_plan.el_name(wt) for wt in FilteredElementCollector(self.doc).OfClass(WallType))

    # ---------- write ----------
    def set_param(self, element_id, name, value):
        el = self._element(element_id)
        p, scope, owner = fix_plan.find_param(self.doc, el, name)
        if p is None or p.IsReadOnly or p.StorageType not in tuple(fix_plan.SUPPORTED) + (StorageType.ElementId,):
            raise ActionError("id %s: '%s' missing, read-only or unsupported" % (_int(element_id), name))
        tid = _int(fix_plan.id_int(owner.Id))
        affected = 1
        if scope == "type":
            affected = fix_plan.count_instances_of_type(self.doc, el.Category, owner.Id)
        target_value = value
        if p.StorageType == StorageType.ElementId:   # family 6: level-reference parameters
            target_value, value = self._id_value(value)
        # no-op changes are skipped: nothing recorded, nothing set (cards list only real changes)
        if p.StorageType == StorageType.ElementId:
            if fix_plan.id_int(p.AsElementId()) == fix_plan.id_int(target_value):
                return False
        elif p.StorageType == StorageType.String and (p.AsString() or u"") == _txt(target_value):
            return False
        self._record((tid, name), {
            "target_id": tid,
            "scope": "new element" if tid in self._created else scope,
            "label": fix_plan.el_name(owner) if self._is_model(el) else "NON-MODEL %s: %s" % (el.Category.Name if el.Category is not None else el.GetType().Name, fix_plan.el_name(owner)),
            "param_name": name,
            "old": p.AsValueString() or p.AsString() or u"",
            "new": _txt(value),
            "affected": int(affected),
        })
        if not _set(p, target_value):
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

    def _points(self, el):
        loc = el.Location
        try:
            pt = loc.Point
            return [(pt.X, pt.Y, pt.Z)]
        except Exception:
            pass
        try:
            c = loc.Curve
            a, b = c.GetEndPoint(0), c.GetEndPoint(1)
            return [(a.X, a.Y, a.Z), (b.X, b.Y, b.Z)]
        except Exception:
            return []

    def _check_bounds(self, el):
        for p in self._points(el):
            if max(abs(_m(v)) for v in p) > MAX_COORD_M:
                raise ActionError("id %s would end up outside +/-%d m of the project origin" % (_int(fix_plan.id_int(el.Id)), MAX_COORD_M))

    def get_line(self, element_id):
        el = self._element(element_id)
        pts = self._points(el)
        if len(pts) == 2:
            a = [round(_m(v), 3) for v in pts[0]]
            b = [round(_m(v), 3) for v in pts[1]]
            return {"start": a, "end": b, "length_m": round(math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3))), 3)}
        if len(pts) == 1:
            return {"point": [round(_m(v), 3) for v in pts[0]]}
        return None

    def move_element(self, element_id, dx, dy, dz=0):
        el = self._element(element_id)
        d = self._offset(el, dx, dy, dz)
        eid = _int(fix_plan.id_int(el.Id))
        tot = self._moves.get(eid, (0.0, 0.0, 0.0))
        tot = (tot[0] + d[0], tot[1] + d[1], tot[2] + d[2])
        if max(abs(v) for v in tot) > MAX_COORD_M:
            raise ActionError("total move of id %s in one action exceeds +/-%d m (the limit applies to the sum of all moves)" % (eid, MAX_COORD_M))
        self._moves[eid] = tot
        before = self._where(el)
        ElementTransformUtils.MoveElement(self.doc, el.Id, XYZ(_ft(d[0]), _ft(d[1]), _ft(d[2])))
        self.doc.Regenerate()
        self._check_bounds(el)
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
            if ne is not None:
                self._check_bounds(ne)
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

    def get_location(self, element_id):
        return self._where(self._element(element_id))

    def _symbols(self, category):
        bic = _FAMILY_CATEGORIES.get(category)   # family 2: any family category
        if bic is None:
            raise ActionError("unknown family category %r; available: %s" % (category, ", ".join(sorted(_FAMILY_CATEGORIES))))
        out = []
        for s in FilteredElementCollector(self.doc).OfClass(FamilySymbol).OfCategory(bic):
            name = fix_plan.el_name(s)
            out.append((s, name, "%s: %s" % (s.FamilyName, name)))
        return out

    def list_family_types(self, category):
        return sorted(full for s, n, full in self._symbols(category))

    def _place(self, category, kind, wall_id, type_name, distance_m, sill_m):
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        wall = self._element(wall_id)
        wid = _int(fix_plan.id_int(wall.Id))
        if not isinstance(wall, Wall):
            raise ActionError("id %s is not a wall" % wid)
        syms = self._symbols(category)
        hits = [s for s, n, full in syms if full == type_name] or [s for s, n, full in syms if n == type_name]
        if not hits:
            raise ActionError("no %s type %r; available: %s" % (kind, type_name, ", ".join(sorted(f for s, n, f in syms))[:400]))
        if len(hits) > 1:
            raise ActionError("type name %r is ambiguous; use 'Family: Type'" % type_name)
        sym = hits[0]
        curve = wall.Location.Curve
        length_m = _m(curve.Length)
        dist = _num(distance_m, "distance_m")
        if not 0.0 < dist < length_m:
            raise ActionError("distance_m must be between 0 and the wall length (%.2f m)" % length_m)
        if not sym.IsActive:
            sym.Activate()
            self.doc.Regenerate()
        pt = curve.Evaluate(dist / length_m, True)
        level = self.doc.GetElement(wall.LevelId)
        inst = self.doc.Create.NewFamilyInstance(pt, sym, wall, level, StructuralType.NonStructural)
        host_txt = "the new wall" if wid in self._created else "wall %s" % wid
        text = "'%s: %s' in %s at %.2f m from its start" % (sym.FamilyName, fix_plan.el_name(sym), host_txt, dist)
        if sill_m is not None:
            sill = _num(sill_m, "sill_height_m")
            if not 0.0 <= sill <= 10.0:
                raise ActionError("sill_height_m must be between 0 and 10 m")
            p = inst.get_Parameter(BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
            if p is None or p.IsReadOnly:
                raise ActionError("this %s type has no editable sill height" % kind)
            p.Set(_ft(sill))
            text += ", sill %.2f m" % sill
        self.doc.Regenerate()
        host = getattr(inst, "Host", None)
        if host is None or fix_plan.id_int(host.Id) != fix_plan.id_int(wall.Id):
            raise ActionError("Revit did not host the new %s in wall %s" % (kind, wid))
        nid = _int(fix_plan.id_int(inst.Id))
        self._created.add(nid)
        self._record((nid, "(new %s)" % kind), {
            "target_id": nid,
            "scope": "created",
            "label": category,
            "param_name": "(new %s)" % kind,
            "old": u"",
            "new": text,
            "affected": 1,
        })
        return nid

    def place_door(self, wall_id, type_name, distance_m):
        return self._place("Doors", "door", wall_id, type_name, distance_m, None)

    def place_window(self, wall_id, type_name, distance_m, sill_height_m=None):
        return self._place("Windows", "window", wall_id, type_name, distance_m, sill_height_m)

    def _center(self, el):
        pts = self._points(el)
        if not pts:
            return None
        if len(pts) == 1:
            return pts[0]
        return ((pts[0][0] + pts[1][0]) / 2.0, (pts[0][1] + pts[1][1]) / 2.0, (pts[0][2] + pts[1][2]) / 2.0)

    def _pose(self, el):
        w = self._where(el)
        try:
            return "%s, rotation %.1f deg" % (w, math.degrees(el.Location.Rotation))
        except Exception:
            return w

    def rotate_element(self, element_id, angle_deg, cx=None, cy=None):   # family 1
        el = self._element(element_id)
        eid = _int(fix_plan.id_int(el.Id))
        a = _num(angle_deg, "angle_deg")
        if a == 0 or abs(a) > 360:
            raise ActionError("angle_deg must be non-zero and between -360 and 360")
        if getattr(el, "Pinned", False):
            raise ActionError("id %s is pinned; unpin it in Revit first" % eid)
        before = self._pose(el)
        if before is None:
            raise ActionError("id %s has no location that can be rotated" % eid)
        if cx is None or cy is None:
            c = self._center(el)
            px, py = c[0], c[1]
        else:
            px, py = _ft(_num(cx, "cx")), _ft(_num(cy, "cy"))
        axis = Line.CreateBound(XYZ(px, py, 0), XYZ(px, py, 1))
        ElementTransformUtils.RotateElement(self.doc, el.Id, axis, math.radians(a))
        self.doc.Regenerate()
        self._check_bounds(el)
        after = self._pose(el)
        if after == before:
            raise ActionError("the rotation had no effect on id %s (Revit kept it in place)" % eid)
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

    def mirror_element(self, element_id, x1, y1, x2, y2, copy=True):   # family 1
        el = self._element(element_id)
        eid = _int(fix_plan.id_int(el.Id))
        p = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in p) > MAX_COORD_M:
            raise ActionError("mirror line coordinates must be within +/-%d m" % MAX_COORD_M)
        dx, dy = p[2] - p[0], p[3] - p[1]
        if math.hypot(dx, dy) < 0.001:
            raise ActionError("the mirror line needs two different points")
        if self._where(el) is None:
            raise ActionError("id %s has no location that can be mirrored" % eid)
        plane = Plane.CreateByNormalAndOrigin(XYZ(-dy, dx, 0).Normalize(), XYZ(_ft(p[0]), _ft(p[1]), 0))
        from System.Collections.Generic import List
        ids = List[ElementId]()
        ids.Add(el.Id)
        if copy:
            if len(self._created) >= MAX_CREATED:
                raise ActionError("more than %d new elements in one action" % MAX_CREATED)
            new_ids = ElementTransformUtils.MirrorElements(self.doc, ids, plane, True)
            self.doc.Regenerate()
            out = []
            for nid in new_ids:
                n = _int(fix_plan.id_int(nid))
                if len(self._created) >= MAX_CREATED:
                    raise ActionError("more than %d new elements in one action" % MAX_CREATED)
                self._created.add(n)
                ne = self.doc.GetElement(nid)
                if ne is not None:
                    self._check_bounds(ne)
                self._record((n, "(mirror)"), {
                    "target_id": n,
                    "scope": "created",
                    "label": ne.Category.Name if ne is not None and ne.Category is not None else "element",
                    "param_name": "(mirror)",
                    "old": u"",
                    "new": "mirror of id %s: %s" % (eid, (self._where(ne) if ne is not None else None) or "no location"),
                    "affected": 1,
                })
                out.append(n)
            return out
        if getattr(el, "Pinned", False):
            raise ActionError("id %s is pinned; unpin it in Revit first" % eid)
        before = self._pose(el)
        ElementTransformUtils.MirrorElements(self.doc, ids, plane, False)
        self.doc.Regenerate()
        self._check_bounds(el)
        after = self._pose(el)
        if after == before:
            raise ActionError("the mirror had no effect on id %s" % eid)
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

    def place_instance(self, type_name, x, y, level_name, rotation_deg=0, category=None):   # family 2
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        cats = [category] if category else sorted(_FAMILY_CATEGORIES)
        hits = []
        for cat in cats:
            for s, n, full in self._symbols(cat):
                if full == type_name or n == type_name:
                    hits.append((s, cat, full))
        seen, uniq = set(), []   # category aliases (Columns / Structural Columns) list the same type twice
        for h in hits:
            k = _int(fix_plan.id_int(h[0].Id))
            if k not in seen:
                seen.add(k)
                uniq.append(h)
        hits = uniq
        exact = [h for h in hits if h[2] == type_name]
        if exact:
            hits = exact
        if not hits:
            raise ActionError("no loaded family type %r%s; list names with list_family_types(category)" % (type_name, (" in " + category) if category else ""))
        if len(hits) > 1:
            raise ActionError("type name %r is ambiguous (%s); use 'Family: Type' or give the category" % (type_name, ", ".join(sorted(set(h[2] + " [" + h[1] + "]" for h in hits)))[:300]))
        sym, cat, full = hits[0]
        if cat in ("Doors", "Windows"):
            raise ActionError("doors and windows need a host wall: use place_door or place_window")
        try:
            ptype = str(sym.Family.FamilyPlacementType)
        except Exception:
            ptype = "OneLevelBased"
        if ptype not in ("OneLevelBased", "TwoLevelsBased"):
            raise ActionError("%r is a %s family; only level-based families can be placed at a point" % (full, ptype))
        lv = self._by_name(Level, level_name, "level")
        xs = [_num(v, "coordinate") for v in (x, y)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        rot = _num(rotation_deg, "rotation_deg")
        if abs(rot) > 360:
            raise ActionError("rotation_deg must be between -360 and 360")
        if not sym.IsActive:
            sym.Activate()
            self.doc.Regenerate()
        if cat == "Structural Framing":
            raise ActionError("beams and braces are placed along a line: use create_beam or create_brace")
        st = StructuralType.Column if cat in ("Columns", "Structural Columns") else StructuralType.NonStructural
        inst = self.doc.Create.NewFamilyInstance(XYZ(_ft(xs[0]), _ft(xs[1]), lv.Elevation), sym, lv, st)
        self.doc.Regenerate()
        if rot:
            pt = inst.Location.Point
            ElementTransformUtils.RotateElement(self.doc, inst.Id, Line.CreateBound(pt, XYZ(pt.X, pt.Y, pt.Z + 1)), math.radians(rot))
            self.doc.Regenerate()
        self._check_bounds(inst)
        nid = _int(fix_plan.id_int(inst.Id))
        self._created.add(nid)
        text = "'%s' at (%.2f, %.2f) m on %s" % (full, xs[0], xs[1], fix_plan.el_name(lv))
        if rot:
            text += ", rotated %.1f deg" % rot
        self._record((nid, "(new instance)"), {
            "target_id": nid,
            "scope": "created",
            "label": inst.Category.Name if inst.Category is not None else cat,
            "param_name": "(new instance)",
            "old": u"",
            "new": text,
            "affected": 1,
        })
        return nid

    def _names_of(self, cls):
        return [fix_plan.el_name(e) for e in FilteredElementCollector(self.doc).OfClass(cls)]

    def create_level(self, name, elevation_m, create_plan=False):   # family 3
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        name = _txt(name).strip()
        if not name:
            raise ActionError("a level needs a name")
        if name in self._names_of(Level):
            raise ActionError("a level named %r already exists" % name)
        z = _num(elevation_m, "elevation_m")
        if abs(z) > MAX_COORD_M:
            raise ActionError("elevation must be within +/-%d m" % MAX_COORD_M)
        for lv in FilteredElementCollector(self.doc).OfClass(Level):
            if abs(_m(lv.Elevation) - z) < 0.001:
                raise ActionError("level %r already uses elevation %.3f m" % (fix_plan.el_name(lv), z))
        lv = Level.Create(self.doc, _ft(z))
        lv.Name = name
        nid = _int(fix_plan.id_int(lv.Id))
        self._created.add(nid)
        self._record((nid, "(new level)"), {
            "target_id": nid, "scope": "created", "label": "Levels", "param_name": "(new level)",
            "old": u"", "new": "level '%s' at %.2f m" % (name, z), "affected": 1,
        })
        if create_plan:
            from Autodesk.Revit.DB import ViewFamilyType, ViewFamily, ViewPlan
            vft = [t for t in FilteredElementCollector(self.doc).OfClass(ViewFamilyType) if t.ViewFamily == ViewFamily.FloorPlan]
            if not vft:
                raise ActionError("no floor plan view type in this project")
            if len(self._created) >= MAX_CREATED:
                raise ActionError("more than %d new elements in one action" % MAX_CREATED)
            v = ViewPlan.Create(self.doc, vft[0].Id, lv.Id)
            vid = _int(fix_plan.id_int(v.Id))
            self._created.add(vid)
            self._record((vid, "(new view)"), {
                "target_id": vid, "scope": "created", "label": "Views", "param_name": "(new view)",
                "old": u"", "new": "floor plan '%s' for level '%s'" % (fix_plan.el_name(v), name), "affected": 1,
            })
        return nid

    def create_grid(self, name, x1, y1, x2, y2):   # family 3
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        name = _txt(name).strip()
        if not name:
            raise ActionError("a grid needs a name")
        if name in self._names_of(Grid):
            raise ActionError("a grid named %r already exists" % name)
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        if math.hypot(xs[2] - xs[0], xs[3] - xs[1]) < 0.1:
            raise ActionError("a grid line must be at least 0.1 m long")
        g = Grid.Create(self.doc, Line.CreateBound(XYZ(_ft(xs[0]), _ft(xs[1]), 0), XYZ(_ft(xs[2]), _ft(xs[3]), 0)))
        g.Name = name
        nid = _int(fix_plan.id_int(g.Id))
        self._created.add(nid)
        self._record((nid, "(new grid)"), {
            "target_id": nid, "scope": "created", "label": "Grids", "param_name": "(new grid)",
            "old": u"", "new": "grid '%s' from (%.2f, %.2f) to (%.2f, %.2f) m" % (name, xs[0], xs[1], xs[2], xs[3]), "affected": 1,
        })
        return nid

    def _room(self, room_id):
        r = self._element(room_id)
        if r.Category is None or r.Category.Name != "Rooms":
            raise ActionError("id %s is not a room" % _int(room_id))
        try:
            area = r.Area
        except Exception:
            area = 0
        if not area or area <= 0:
            raise ActionError("room %s is not placed or not enclosed, so it has no boundary" % _int(room_id))
        return r

    def _room_loops(self, r):
        from Autodesk.Revit.DB import SpatialElementBoundaryOptions, CurveLoop
        from System.Collections.Generic import List
        loops = List[CurveLoop]()
        for segs in r.GetBoundarySegments(SpatialElementBoundaryOptions()):
            cl = CurveLoop()
            for s in segs:
                cl.Append(s.GetCurve())
            loops.Add(cl)
        if loops.Count == 0:
            raise ActionError("room %s has no boundary" % _int(fix_plan.id_int(r.Id)))
        return loops

    def _room_label(self, r):
        try:
            num = r.Number
        except Exception:
            num = None
        return ("room " + _txt(num)) if num else ("room id %s" % _int(fix_plan.id_int(r.Id)))

    def _type_id(self, cls, name, what, group):
        if name:
            return self._by_name(cls, name, what)
        return self.doc.GetElement(self.doc.GetDefaultElementTypeId(group))

    def list_floor_types(self):
        from Autodesk.Revit.DB import FloorType
        return sorted(fix_plan.el_name(t) for t in FilteredElementCollector(self.doc).OfClass(FloorType))

    def list_ceiling_types(self):
        from Autodesk.Revit.DB import CeilingType
        return sorted(fix_plan.el_name(t) for t in FilteredElementCollector(self.doc).OfClass(CeilingType))

    def _record_new(self, el, label, text, kind):
        nid = _int(fix_plan.id_int(el.Id))
        self._created.add(nid)
        self._record((nid, kind), {"target_id": nid, "scope": "created", "label": label, "param_name": kind,
                                   "old": u"", "new": text, "affected": 1})
        return nid

    def create_floor_in_room(self, room_id, floor_type_name=None):   # family 4
        from Autodesk.Revit.DB import Floor, FloorType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        r = self._room(room_id)
        ft = self._type_id(FloorType, floor_type_name, "floor type", ElementTypeGroup.FloorType)
        f = Floor.Create(self.doc, self._room_loops(r), ft.Id, r.LevelId)
        self.doc.Regenerate()
        lvname = fix_plan.el_name(self.doc.GetElement(r.LevelId))
        return self._record_new(f, "Floors", "floor '%s' on %s from %s" % (fix_plan.el_name(ft), lvname, self._room_label(r)), "(new floor)")

    def create_floor(self, level_name, x1, y1, x2, y2, floor_type_name=None):   # family 4
        from Autodesk.Revit.DB import Floor, FloorType, CurveLoop
        from System.Collections.Generic import List
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lv = self._by_name(Level, level_name, "level")
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        a, b = (min(xs[0], xs[2]), min(xs[1], xs[3])), (max(xs[0], xs[2]), max(xs[1], xs[3]))
        if (b[0] - a[0]) * (b[1] - a[1]) < 0.1:
            raise ActionError("the floor rectangle must be at least 0.1 m2")
        z = lv.Elevation
        p = [XYZ(_ft(a[0]), _ft(a[1]), z), XYZ(_ft(b[0]), _ft(a[1]), z), XYZ(_ft(b[0]), _ft(b[1]), z), XYZ(_ft(a[0]), _ft(b[1]), z)]
        cl = CurveLoop()
        for i in range(4):
            cl.Append(Line.CreateBound(p[i], p[(i + 1) % 4]))
        loops = List[CurveLoop]()
        loops.Add(cl)
        ft = self._type_id(FloorType, floor_type_name, "floor type", ElementTypeGroup.FloorType)
        f = Floor.Create(self.doc, loops, ft.Id, lv.Id)
        self.doc.Regenerate()
        return self._record_new(f, "Floors", "floor '%s' on %s, rectangle (%.2f, %.2f) to (%.2f, %.2f) m"
                                % (fix_plan.el_name(ft), fix_plan.el_name(lv), a[0], a[1], b[0], b[1]), "(new floor)")

    def create_ceiling_in_room(self, room_id, height_m, ceiling_type_name=None):   # family 4
        from Autodesk.Revit.DB import Ceiling, CeilingType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        h = _num(height_m, "height_m")
        if not 0.5 <= h <= 30:
            raise ActionError("ceiling height must be between 0.5 and 30 m")
        r = self._room(room_id)
        ct = self._type_id(CeilingType, ceiling_type_name, "ceiling type", ElementTypeGroup.CeilingType)
        c = Ceiling.Create(self.doc, self._room_loops(r), ct.Id, r.LevelId)
        p = c.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
        if p is None or p.IsReadOnly:
            raise ActionError("this ceiling type has no editable height offset")
        p.Set(_ft(h))
        self.doc.Regenerate()
        lvname = fix_plan.el_name(self.doc.GetElement(r.LevelId))
        return self._record_new(c, "Ceilings", "ceiling '%s' at %.2f m in %s on %s" % (fix_plan.el_name(ct), h, self._room_label(r), lvname), "(new ceiling)")

    def _id_value(self, value):   # family 6
        s = _txt(value).strip()
        if s.lower() in ("none", "", "unconnected"):
            return ElementId.InvalidElementId, "none"
        try:
            el = self.doc.GetElement(fix_plan.make_id(int(s)))
            if el is not None:
                return el.Id, fix_plan.el_name(el)
        except ValueError:
            pass
        for lv in FilteredElementCollector(self.doc).OfClass(Level):
            if fix_plan.el_name(lv) == s:
                return lv.Id, s
        raise ActionError("%r is not a level name or element id; for parameters that hold a level (Top Constraint, Base Constraint) "
                          "give a level name: %s" % (s, ", ".join(self._names_of(Level))))

    def _wall(self, wall_id):
        w = self._element(wall_id)
        if not isinstance(w, Wall):
            raise ActionError("id %s is not a wall" % _int(wall_id))
        return w

    def _ends(self, state):
        names = [n for n, b in zip(("start", "end"), state) if b]
        return ", ".join(names) if names else "neither end"

    def _wall_joins(self, wall_id, allow):
        from Autodesk.Revit.DB import WallUtils
        w = self._wall(wall_id)
        wid = _int(fix_plan.id_int(w.Id))
        before = [WallUtils.IsWallJoinAllowedAtEnd(w, i) for i in (0, 1)]
        todo = [i for i in (0, 1) if before[i] != allow]
        if not todo:
            raise ActionError("wall %s already has joins %s at both ends" % (wid, "allowed" if allow else "disallowed"))
        for i in todo:
            if allow:
                WallUtils.AllowWallJoinAtEnd(w, i)
            else:
                WallUtils.DisallowWallJoinAtEnd(w, i)
        self.doc.Regenerate()
        after = [WallUtils.IsWallJoinAllowedAtEnd(w, i) for i in (0, 1)]
        self._record((wid, "(join)"), {
            "target_id": wid, "scope": "new element" if wid in self._created else "instance", "label": "Walls",
            "param_name": "(join)", "old": "joins allowed at " + self._ends(before),
            "new": "joins allowed at " + self._ends(after), "affected": 1})
        return True

    def unjoin_walls(self, a_id, b_id):   # C32: release the join between wall A and wall B only (at A's end where B is joined)
        from Autodesk.Revit.DB import WallUtils
        a = self._wall(a_id)
        aid, bid = _int(fix_plan.id_int(a.Id)), _int(b_id)
        if aid == bid:
            raise ActionError("a wall cannot be unjoined from itself")
        names = ("start", "end")
        done, others = [], []
        for i in (0, 1):
            try:
                at = [_int(fix_plan.id_int(e.Id)) for e in a.Location.get_ElementsAtJoin(i)]
            except Exception:
                at = []
            at = [x for x in at if x != aid]
            if bid in at:
                WallUtils.DisallowWallJoinAtEnd(a, i)
                done.append(names[i])
                others.extend([x for x in at if x != bid])
        if not done:
            raise ActionError("walls %s and %s are not joined at either end of wall %s" % (aid, bid, aid))
        self.doc.Regenerate()
        text = "unjoined from id %s at %s" % (bid, " and ".join(done))
        if others:
            text += " (Revit releases the whole end, so the joins with ids %s at that end are released too)" % ", ".join(str(x) for x in sorted(set(others)))
        self._record((aid, "(join %s)" % bid), {
            "target_id": aid, "scope": "new element" if aid in self._created else "instance", "label": "Walls",
            "param_name": "(join)", "old": "joined with id %s at %s" % (bid, " and ".join(done)), "new": text, "affected": 1})
        return True

    def unjoin_wall(self, wall_id):   # family 6: Disallow Join at both ends
        return self._wall_joins(wall_id, False)

    def allow_wall_joins(self, wall_id):   # family 6: Allow Join at both ends
        return self._wall_joins(wall_id, True)

    def _geometry_join(self, a_id, b_id, join):
        from Autodesk.Revit.DB import JoinGeometryUtils
        a = self._element(a_id)
        b = self._element(b_id)
        aid, bid = _int(fix_plan.id_int(a.Id)), _int(fix_plan.id_int(b.Id))
        joined = JoinGeometryUtils.AreElementsJoined(self.doc, a, b)
        if joined == join:
            raise ActionError("ids %s and %s are already %s" % (aid, bid, "joined" if join else "not joined"))
        if join:
            JoinGeometryUtils.JoinGeometry(self.doc, a, b)
        else:
            JoinGeometryUtils.UnjoinGeometry(self.doc, a, b)
        self.doc.Regenerate()
        self._record((aid, "(join)"), {
            "target_id": aid, "scope": "new element" if aid in self._created else "instance",
            "label": a.Category.Name if a.Category is not None else "element", "param_name": "(join)",
            "old": ("not joined with id %s" if join else "joined with id %s") % bid,
            "new": ("geometry joined with id %s" if join else "geometry unjoined from id %s") % bid, "affected": 1})
        return True

    def join_geometry(self, a_id, b_id):   # family 6
        return self._geometry_join(a_id, b_id, True)

    def unjoin_geometry(self, a_id, b_id):   # family 6
        return self._geometry_join(a_id, b_id, False)

    def _view(self):
        v = self.doc.ActiveView
        if v is None:
            raise ActionError("there is no active view")
        return v

    def tag_elements(self, element_ids=None, category=None, with_leader=False):   # family 7
        from Autodesk.Revit.DB import Reference, IndependentTag, TagMode, TagOrientation
        view = self._view()
        ids = []
        if element_ids:
            ids = [_int(i) for i in element_ids]
        elif category:
            bic = _FAMILY_CATEGORIES.get(category)
            if bic is None and category == "Walls":
                bic = BuiltInCategory.OST_Walls
            if bic is None and category == "Rooms":
                bic = BuiltInCategory.OST_Rooms
            if bic is None:
                raise ActionError("unknown category %r for tagging" % category)
            ids = [_int(fix_plan.id_int(e.Id)) for e in FilteredElementCollector(self.doc, view.Id).OfCategory(bic).WhereElementIsNotElementType()]
        else:
            raise ActionError("give element_ids or a category to tag")
        tagged = set()
        for t in FilteredElementCollector(self.doc, view.Id).OfClass(IndependentTag):
            try:
                for x in t.GetTaggedLocalElementIds():
                    tagged.add(_int(fix_plan.id_int(x)))
            except Exception:
                try:
                    tagged.add(_int(fix_plan.id_int(t.TaggedLocalElementId)))
                except Exception:
                    pass
        what = category or "elements"
        if not ids:
            raise ActionError("no %s are visible in view '%s' (a temporary hide or isolate may be active; reset the view first)" % (what, fix_plan.el_name(view)))
        made = []
        for n in ids:
            if n in tagged:
                continue
            if len(self._created) >= MAX_CREATED:
                raise ActionError("more than %d new elements in one action" % MAX_CREATED)
            el = self._element(n)
            c = self._center(el)
            if c is None:
                raise ActionError("id %s has no location to tag" % n)
            try:
                tag = IndependentTag.Create(self.doc, view.Id, Reference(el), bool(with_leader), TagMode.TM_ADDBY_CATEGORY,
                                            TagOrientation.Horizontal, XYZ(c[0], c[1], c[2]))
            except Exception as ex:
                raise ActionError("could not tag id %s in view '%s' (is a tag family loaded for this category?): %s" % (n, fix_plan.el_name(view), ex))
            label = tag.Category.Name if tag.Category is not None else "Tags"
            made.append(self._record_new(tag, label, "tag for id %s in view '%s'" % (n, fix_plan.el_name(view)), "(new tag)"))
        if not made:
            raise ActionError("all %d %s visible in view '%s' are already tagged; nothing to add" % (len(ids), what, fix_plan.el_name(view)))
        return made

    def add_text_note(self, text, x=None, y=None, near_element_id=None):   # family 7
        from Autodesk.Revit.DB import TextNote
        view = self._view()
        s = _txt(text).strip()
        if not 1 <= len(s) <= 500:
            raise ActionError("text must be 1-500 characters")
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        if near_element_id is not None:
            c = self._center(self._element(near_element_id))
            if c is None:
                raise ActionError("id %s has no location" % _int(near_element_id))
            px, py = c[0] + _ft(1.0), c[1]
            where = "next to id %s" % _int(near_element_id)
        else:
            xs = [_num(v, "coordinate") for v in (x, y)]
            if max(abs(v) for v in xs) > MAX_COORD_M:
                raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
            px, py = _ft(xs[0]), _ft(xs[1])
            where = "at (%.2f, %.2f) m" % (xs[0], xs[1])
        tid = self.doc.GetDefaultElementTypeId(ElementTypeGroup.TextNoteType)
        note = TextNote.Create(self.doc, view.Id, XYZ(px, py, 0), s, tid)
        return self._record_new(note, "Text Notes", "text note '%s' %s in view '%s'" % (s[:120], where, fix_plan.el_name(view)), "(new text note)")

    def create_sheet(self, number, name, title_block=None):   # family 7
        from Autodesk.Revit.DB import ViewSheet
        num = _txt(number).strip()
        nm = _txt(name).strip()
        if not num or not nm:
            raise ActionError("a sheet needs a number and a name")
        for sh in FilteredElementCollector(self.doc).OfClass(ViewSheet):
            if sh.SheetNumber == num:
                raise ActionError("a sheet numbered %r already exists" % num)
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        tbs = [s for s in FilteredElementCollector(self.doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_TitleBlocks)]
        tb = ElementId.InvalidElementId
        tbname = "no title block"
        if title_block:
            hits = [s for s in tbs if fix_plan.el_name(s) == title_block or ("%s: %s" % (s.FamilyName, fix_plan.el_name(s))) == title_block]
            if not hits:
                raise ActionError("no title block %r; available: %s" % (title_block, ", ".join(sorted("%s: %s" % (s.FamilyName, fix_plan.el_name(s)) for s in tbs))[:300]))
            tb, tbname = hits[0].Id, title_block
        elif tbs:
            tb, tbname = tbs[0].Id, "%s: %s" % (tbs[0].FamilyName, fix_plan.el_name(tbs[0]))
        sh = ViewSheet.Create(self.doc, tb)
        sh.SheetNumber = num
        sh.Name = nm
        return self._record_new(sh, "Sheets", "sheet '%s - %s' (%s)" % (num, nm, tbname), "(new sheet)")

    def list_sheets(self):   # family 7
        from Autodesk.Revit.DB import ViewSheet
        out = [{"id": _int(fix_plan.id_int(s.Id)), "number": s.SheetNumber, "name": fix_plan.el_name(s)}
               for s in FilteredElementCollector(self.doc).OfClass(ViewSheet)]
        return sorted(out, key=lambda x: x["number"])


    def get_elements(self, category):   # C16: same output as revit_ro.get_elements
        extra = {"Walls": "OST_Walls", "Rooms": "OST_Rooms", "Levels": "OST_Levels", "Floors": "OST_Floors", "Ceilings": "OST_Ceilings"}
        bic = _FAMILY_CATEGORIES.get(category)
        if bic is None and category in extra:
            bic = getattr(BuiltInCategory, extra[category], None)
        if bic is None:
            raise ActionError("unknown category %r; available: %s" % (category, ", ".join(sorted(list(_FAMILY_CATEGORIES) + list(extra)))))
        return [{"id": _int(fix_plan.id_int(e.Id)), "name": fix_plan.el_name(e), "category": category}
                for e in FilteredElementCollector(self.doc).OfCategory(bic).WhereElementIsNotElementType()]


    def get_wall_joins(self, wall_id):   # C18: same as revit_ro.get_wall_joins
        w = self._wall(wall_id)
        me = _int(fix_plan.id_int(w.Id))
        out = {}
        for i, key in ((0, "start"), (1, "end")):
            ids = []
            try:
                for e in w.Location.get_ElementsAtJoin(i):
                    n = _int(fix_plan.id_int(e.Id))
                    if n != me:
                        ids.append(n)
            except Exception:
                pass
            out[key] = sorted(ids)
        return out


    # ---- Schedules (roadmap feature 1, step 1) ----
    def _schedules(self):
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

    def _schedule_bic(self, category):
        extra = {"Walls": "OST_Walls", "Rooms": "OST_Rooms", "Floors": "OST_Floors", "Ceilings": "OST_Ceilings"}
        bic = _FAMILY_CATEGORIES.get(category)
        if bic is None and category in extra:
            bic = getattr(BuiltInCategory, extra[category], None)
        if bic is None:
            raise ActionError("unknown schedule category %r; available: %s" % (category, ", ".join(sorted(list(_FAMILY_CATEGORIES) + list(extra)))))
        return bic

    def list_schedulable_fields(self, category):   # read-only: a temporary schedule is made and deleted
        from Autodesk.Revit.DB import ViewSchedule
        vs = ViewSchedule.CreateSchedule(self.doc, ElementId(self._schedule_bic(category)))
        try:
            names = sorted(set(f.GetName(self.doc) for f in vs.Definition.GetSchedulableFields()))
        finally:
            self.doc.Delete(vs.Id)
        return names

    def list_schedules(self):
        return sorted([{"id": _int(fix_plan.id_int(s.Id)), "name": fix_plan.el_name(s)} for s in self._schedules()], key=lambda x: x["name"])

    def _find_schedule(self, schedule):
        key = _txt(schedule).strip()
        for s in self._schedules():
            if fix_plan.el_name(s) == key or str(_int(fix_plan.id_int(s.Id))) == key:
                return s
        raise ActionError("no schedule %r; existing: %s" % (key, ", ".join(sorted(fix_plan.el_name(s) for s in self._schedules()))[:300]))

    def read_schedule(self, schedule, max_rows=200):
        from Autodesk.Revit.DB import SectionType
        s = self._find_schedule(schedule)
        body = s.GetTableData().GetSectionData(SectionType.Body)
        rows = []
        for r in range(body.NumberOfRows):
            rows.append([s.GetCellText(SectionType.Body, r, c) for c in range(body.NumberOfColumns)])
        cols = rows[0] if rows else []
        data = [x for x in rows[1:] if any(_txt(c).strip() for c in x)]   # row 0 = headings; blank spacer rows dropped
        return {"name": fix_plan.el_name(s), "id": _int(fix_plan.id_int(s.Id)), "columns": cols, "rows": data[:int(max_rows)], "row_count": len(data)}

    def create_schedule(self, category, fields, name=None, sort_by=None, filters=None):
        from Autodesk.Revit.DB import ViewSchedule, ScheduleSortGroupField, ScheduleFilter, ScheduleFilterType, SectionType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        bic = self._schedule_bic(category)
        want = [_txt(f).strip() for f in (fields or []) if _txt(f).strip()]
        if not want:
            raise ActionError("a schedule needs at least one field")
        taken = set(fix_plan.el_name(s) for s in self._schedules())
        def _free(base):
            if base not in taken:
                return base
            i = 2
            while ("%s %d" % (base, i)) in taken:
                i += 1
            return "%s %d" % (base, i)
        if name:
            nm = _txt(name).strip()
            if nm in taken:
                raise ActionError("a schedule named %r already exists; a free name is %r (or leave the name out)" % (nm, _free(nm)))
        else:
            nm = _free("%s Schedule (AI)" % category)   # no name given: a free default
        vs = ViewSchedule.CreateSchedule(self.doc, ElementId(bic))
        avail = {}
        for f in vs.Definition.GetSchedulableFields():
            avail.setdefault(f.GetName(self.doc).lower(), f)
        missing = [w for w in want if w.lower() not in avail]
        if missing:
            import difflib
            names = sorted(f.GetName(self.doc) for f in avail.values())
            close = []
            for m in missing:
                close += difflib.get_close_matches(m, names, n=5, cutoff=0.5)
            raise ActionError("no field %s in %s schedules; closest: %s; %d fields in total (list them with list_schedulable_fields('%s'))"
                              % (", ".join(repr(m) for m in missing), category, ", ".join(close) or "none", len(names), category))
        added = {}
        for w in want:
            added[w.lower()] = vs.Definition.AddField(avail[w.lower()])
        vs.Name = nm
        bits = ["fields " + ", ".join(want)]
        if sort_by:
            k = _txt(sort_by).strip().lower()
            if k not in added:
                raise ActionError("sort_by must be one of the schedule's fields: %s" % ", ".join(want))
            vs.Definition.AddSortGroupField(ScheduleSortGroupField(added[k].FieldId))
            bits.append("sorted by " + _txt(sort_by).strip())
        ops = {"=": ScheduleFilterType.Equal, "==": ScheduleFilterType.Equal, "!=": ScheduleFilterType.NotEqual, "contains": ScheduleFilterType.Contains}
        for flt in (filters or []):
            if not isinstance(flt, (list, tuple)) or len(flt) != 3:
                raise ActionError("each filter is [field, operator, value]")
            fld, op, value = _txt(flt[0]).strip(), _txt(flt[1]).strip().lower(), _txt(flt[2]).strip()
            if fld.lower() not in added:
                if fld.lower() not in avail:
                    raise ActionError("no field %r in %s schedules to filter on" % (fld, category))
                added[fld.lower()] = vs.Definition.AddField(avail[fld.lower()])
                added[fld.lower()].IsHidden = True   # Revit filters need the field in the schedule; added hidden
                bits.append("hidden field %s added for the filter" % fld)
            if op not in ops:
                raise ActionError("filter operator must be =, != or contains")
            if fld.lower() == "level":
                lid = None
                for lv in FilteredElementCollector(self.doc).OfClass(Level):
                    if fix_plan.el_name(lv) == value:
                        lid = lv.Id
                if lid is None:
                    raise ActionError("no level %r; levels: %s" % (value, ", ".join(self._names_of(Level))))
                vs.Definition.AddFilter(ScheduleFilter(added["level"].FieldId, ops[op], lid))
            else:
                vs.Definition.AddFilter(ScheduleFilter(added[fld.lower()].FieldId, ops[op], value))
            bits.append("filter %s %s %s" % (fld, op, value))
        self.doc.Regenerate()
        try:
            bits.append("%d rows" % self.read_schedule(_int(fix_plan.id_int(vs.Id)), 0)["row_count"])
        except Exception:
            pass
        return self._record_new(vs, "Schedules", "schedule '%s' (%s): %s" % (nm, category, "; ".join(bits)), "(new schedule)")


    # ---- Schedules step 2: edit and place on a sheet ----
    def _sched_fields(self, vs):
        out = {}
        defn = vs.Definition
        for i in range(defn.GetFieldCount()):
            f = defn.GetField(i)
            out[f.GetName().lower()] = f
        return out

    def _sched_names(self, vs):
        defn = vs.Definition
        return [defn.GetField(i).GetName() for i in range(defn.GetFieldCount()) if not defn.GetField(i).IsHidden]

    def _sched_avail(self, vs):
        avail = {}
        for f in vs.Definition.GetSchedulableFields():
            avail.setdefault(f.GetName(self.doc).lower(), f)
        return avail

    def _sched_record(self, vs, what, key, old, new):
        sid = _int(fix_plan.id_int(vs.Id))
        self._record((sid, what, key), {"target_id": sid, "scope": "new element" if sid in self._created else "instance",
                                       "label": "Schedules", "param_name": what, "old": old, "new": new, "affected": 1})

    def add_schedule_field(self, schedule, field, hidden=False):
        import difflib
        vs = self._find_schedule(schedule)
        name = _txt(field).strip()
        have = self._sched_fields(vs)
        if name.lower() in have:
            raise ActionError("the schedule already has the field %r" % name)
        avail = self._sched_avail(vs)
        if name.lower() not in avail:
            names = sorted(f.GetName(self.doc) for f in avail.values())
            raise ActionError("no field %r for this schedule; closest: %s" % (name, ", ".join(difflib.get_close_matches(name, names, n=5, cutoff=0.5)) or "none"))
        before = ", ".join(self._sched_names(vs))
        f = vs.Definition.AddField(avail[name.lower()])
        if hidden:
            f.IsHidden = True
        self.doc.Regenerate()
        self._sched_record(vs, "(fields)", "add " + name, before, ", ".join(self._sched_names(vs)) + (" (+ hidden %s)" % name if hidden else ""))
        return True

    def remove_schedule_field(self, schedule, field):
        vs = self._find_schedule(schedule)
        name = _txt(field).strip()
        have = self._sched_fields(vs)
        if name.lower() not in have:
            raise ActionError("the schedule has no field %r; its fields: %s" % (name, ", ".join(self._sched_names(vs))))
        if len(self._sched_names(vs)) <= 1 and not have[name.lower()].IsHidden:
            raise ActionError("a schedule needs at least one field; %r is the last one" % name)
        before = ", ".join(self._sched_names(vs))
        vs.Definition.RemoveField(have[name.lower()].FieldId)
        self.doc.Regenerate()
        self._sched_record(vs, "(fields)", "remove " + name, before, ", ".join(self._sched_names(vs)))
        return True

    def set_schedule_sort(self, schedule, field, ascending=True):
        from Autodesk.Revit.DB import ScheduleSortGroupField, ScheduleSortOrder
        vs = self._find_schedule(schedule)
        name = _txt(field).strip()
        have = self._sched_fields(vs)
        if name.lower() not in have:
            raise ActionError("sort field %r must be in the schedule; its fields: %s" % (name, ", ".join(self._sched_names(vs))))
        vs.Definition.ClearSortGroupFields()
        vs.Definition.AddSortGroupField(ScheduleSortGroupField(have[name.lower()].FieldId, ScheduleSortOrder.Ascending if ascending else ScheduleSortOrder.Descending))
        self.doc.Regenerate()
        self._sched_record(vs, "(sort)", "sort", "", "sorted by %s %s" % (name, "ascending" if ascending else "descending"))
        return True

    def set_schedule_filter(self, schedule, filters):
        from Autodesk.Revit.DB import ScheduleFilter, ScheduleFilterType
        vs = self._find_schedule(schedule)
        ops = {"=": ScheduleFilterType.Equal, "==": ScheduleFilterType.Equal, "!=": ScheduleFilterType.NotEqual, "contains": ScheduleFilterType.Contains}
        have = self._sched_fields(vs)
        avail = self._sched_avail(vs)
        vs.Definition.ClearFilters()
        bits = []
        for flt in (filters or []):
            if not isinstance(flt, (list, tuple)) or len(flt) != 3:
                raise ActionError("each filter is [field, operator, value]")
            fld, op, value = _txt(flt[0]).strip(), _txt(flt[1]).strip().lower(), _txt(flt[2]).strip()
            if op not in ops:
                raise ActionError("filter operator must be =, != or contains")
            if fld.lower() not in have:
                if fld.lower() not in avail:
                    raise ActionError("no field %r to filter on" % fld)
                have[fld.lower()] = vs.Definition.AddField(avail[fld.lower()])
                have[fld.lower()].IsHidden = True
                bits.append("hidden field %s added" % fld)
            if fld.lower() == "level":
                lid = None
                for lv in FilteredElementCollector(self.doc).OfClass(Level):
                    if fix_plan.el_name(lv) == value:
                        lid = lv.Id
                if lid is None:
                    raise ActionError("no level %r; levels: %s" % (value, ", ".join(self._names_of(Level))))
                vs.Definition.AddFilter(ScheduleFilter(have["level"].FieldId, ops[op], lid))
            else:
                vs.Definition.AddFilter(ScheduleFilter(have[fld.lower()].FieldId, ops[op], value))
            bits.append("%s %s %s" % (fld, op, value))
        self.doc.Regenerate()
        n = self.read_schedule(_int(fix_plan.id_int(vs.Id)), 0)["row_count"]
        self._sched_record(vs, "(filter)", "filter", "", ("filters: " + "; ".join(bits) if bits else "no filters") + "; %d rows" % n)
        return True

    def place_schedule_on_sheet(self, schedule, sheet_number, x=None, y=None):
        from Autodesk.Revit.DB import ViewSheet, ScheduleSheetInstance
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        vs = self._find_schedule(schedule)
        num = _txt(sheet_number).strip()
        sheets = list(FilteredElementCollector(self.doc).OfClass(ViewSheet))
        sh = [s for s in sheets if s.SheetNumber == num]
        if not sh:
            raise ActionError("no sheet numbered %r; sheets: %s" % (num, ", ".join(sorted(s.SheetNumber for s in sheets))[:300]))
        sh = sh[0]
        if x is None or y is None:
            o = sh.Outline
            pt = XYZ((o.Min.U + o.Max.U) / 2.0, (o.Min.V + o.Max.V) / 2.0, 0)
        else:
            pt = XYZ(_ft(_num(x, "x")), _ft(_num(y, "y")), 0)
        inst = ScheduleSheetInstance.Create(self.doc, sh.Id, vs.Id, pt)
        self.doc.Regenerate()
        label = inst.Category.Name if inst.Category is not None else "Schedule on sheet"
        return self._record_new(inst, label, "schedule '%s' placed on sheet '%s - %s'" % (fix_plan.el_name(vs), sh.SheetNumber, fix_plan.el_name(sh)), "(schedule on sheet)")


    # ---- Views and sheet sets (roadmap feature 2) ----
    def _all_views(self):
        from Autodesk.Revit.DB import View, ViewSheet, ViewSchedule
        return [v for v in FilteredElementCollector(self.doc).OfClass(View) if not v.IsTemplate and not isinstance(v, (ViewSheet, ViewSchedule))]

    def _view_sheet_map(self):
        from Autodesk.Revit.DB import Viewport
        m = {}
        for vp in FilteredElementCollector(self.doc).OfClass(Viewport):
            sh = self.doc.GetElement(vp.SheetId)
            m[_int(fix_plan.id_int(vp.ViewId))] = sh.SheetNumber if sh is not None else "?"
        return m

    def list_views(self, kind=None):
        sm = self._view_sheet_map()
        out = []
        for v in self._all_views():
            vt = str(v.ViewType)
            if kind and _txt(kind).lower() not in vt.lower():
                continue
            lv = None
            try:
                lv = fix_plan.el_name(v.GenLevel) if v.GenLevel is not None else None
            except Exception:
                pass
            vid = _int(fix_plan.id_int(v.Id))
            out.append({"id": vid, "name": fix_plan.el_name(v), "type": vt, "level": lv, "on_sheet": sm.get(vid)})
        return sorted(out, key=lambda x: (x["type"], x["name"]))

    def list_view_templates(self):
        from Autodesk.Revit.DB import View
        return sorted(fix_plan.el_name(v) for v in FilteredElementCollector(self.doc).OfClass(View) if v.IsTemplate)

    def list_title_blocks(self):
        return sorted("%s: %s" % (s.FamilyName, fix_plan.el_name(s)) for s in FilteredElementCollector(self.doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_TitleBlocks))

    def _find_view(self, view):
        key = _txt(view).strip()
        views = self._all_views()
        for v in views:
            if str(_int(fix_plan.id_int(v.Id))) == key:
                return v
        hits = [v for v in views if fix_plan.el_name(v) == key]
        if len(hits) > 1:
            sm = self._view_sheet_map()
            desc = ["id %d (%s%s)" % (_int(fix_plan.id_int(v.Id)), v.ViewType, (", on sheet %s" % sm[_int(fix_plan.id_int(v.Id))]) if _int(fix_plan.id_int(v.Id)) in sm else "") for v in hits]
            raise ActionError("%d views are named %r: %s; give the id" % (len(hits), key, ", ".join(desc)))
        if hits:
            return hits[0]
        raise ActionError("no view %r (use list_views)" % key)

    def _free_view_name(self, base):
        taken = set(fix_plan.el_name(v) for v in self._all_views())
        if base not in taken:
            return base
        i = 2
        while ("%s %d" % (base, i)) in taken:
            i += 1
        return "%s %d" % (base, i)

    def _name_view(self, v, name, default):
        if name:
            nm = _txt(name).strip()
            if nm in set(fix_plan.el_name(x) for x in self._all_views() if x.Id != v.Id):
                raise ActionError("a view named %r already exists; a free name is %r (or leave the name out)" % (nm, self._free_view_name(nm)))
        else:
            nm = self._free_view_name(default)
        v.Name = nm
        return nm

    def _vft(self, family):
        from Autodesk.Revit.DB import ViewFamilyType
        for t in FilteredElementCollector(self.doc).OfClass(ViewFamilyType):
            if t.ViewFamily == family:
                return t
        raise ActionError("this project has no %s view type" % family)

    def _template_and_scale(self, v, template, scale, bits):
        from Autodesk.Revit.DB import View
        if template:
            tn = _txt(template).strip()
            ts = [t for t in FilteredElementCollector(self.doc).OfClass(View) if t.IsTemplate and fix_plan.el_name(t) == tn]
            if not ts:
                raise ActionError("no view template %r; templates: %s" % (tn, ", ".join(self.list_view_templates()) or "none"))
            try:
                v.ViewTemplateId = ts[0].Id
            except Exception as ex:
                raise ActionError("template %r cannot be applied to this view: %s" % (tn, ex))
            bits.append("template '%s'" % tn)
        if scale:
            sc = int(_num(scale, "scale"))
            if not 1 <= sc <= 5000:
                raise ActionError("scale must be between 1 and 5000 (for 1:100 give 100)")
            try:
                v.Scale = sc
            except Exception as ex:
                raise ActionError("Revit refused scale 1:%d for this view (a template may control it): %s" % (sc, ex))
            bits.append("1:%d" % sc)

    def create_plan_view(self, level_name, kind="floor", name=None, template=None, scale=None):
        from Autodesk.Revit.DB import ViewFamily, ViewPlan
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        k = _txt(kind).strip().lower()
        if k not in ("floor", "ceiling"):
            raise ActionError("kind must be floor or ceiling")
        lv = self._by_name(Level, level_name, "level")
        v = ViewPlan.Create(self.doc, self._vft(ViewFamily.FloorPlan if k == "floor" else ViewFamily.CeilingPlan).Id, lv.Id)
        nm = self._name_view(v, name, "%s - %s Plan (AI)" % (fix_plan.el_name(lv), "Floor" if k == "floor" else "Ceiling"))
        bits = []
        self._template_and_scale(v, template, scale, bits)
        return self._record_new(v, "Views", "%s plan '%s' for level %s%s" % (k, nm, fix_plan.el_name(lv), (" (" + ", ".join(bits) + ")") if bits else ""), "(new view)")

    def create_section(self, x1, y1, x2, y2, depth_m=5, name=None):
        from Autodesk.Revit.DB import ViewFamily, ViewSection, BoundingBoxXYZ, Transform
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        dep = _num(depth_m, "depth_m")
        if not 0.1 <= dep <= 200:
            raise ActionError("depth_m must be between 0.1 and 200")
        p0, p1 = XYZ(_ft(xs[0]), _ft(xs[1]), 0), XYZ(_ft(xs[2]), _ft(xs[3]), 0)
        vec = p1.Subtract(p0)
        w = vec.GetLength()
        if w < _ft(0.5):
            raise ActionError("a section line must be at least 0.5 m long")
        elev = sorted(lv.Elevation for lv in FilteredElementCollector(self.doc).OfClass(Level))
        lo, hi = elev[0] - _ft(1), elev[-1] + _ft(4)
        dx = vec.Normalize()
        up = XYZ.BasisZ
        t = Transform.Identity
        t.Origin = p0.Add(vec.Multiply(0.5))
        t.BasisX = dx
        t.BasisY = up
        t.BasisZ = dx.CrossProduct(up)
        box = BoundingBoxXYZ()
        box.Transform = t
        box.Min = XYZ(-w / 2.0, lo, 0)
        box.Max = XYZ(w / 2.0, hi, _ft(dep))
        v = ViewSection.CreateSection(self.doc, self._vft(ViewFamily.Section).Id, box)
        nm = self._name_view(v, name, "Section (AI)")
        return self._record_new(v, "Views", "section '%s' along (%.2f, %.2f) to (%.2f, %.2f) m, depth %.2f m" % (nm, xs[0], xs[1], xs[2], xs[3], dep), "(new view)")

    def create_3d_view(self, name=None):
        from Autodesk.Revit.DB import ViewFamily, View3D
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        v = View3D.CreateIsometric(self.doc, self._vft(ViewFamily.ThreeDimensional).Id)
        nm = self._name_view(v, name, "3D (AI)")
        return self._record_new(v, "Views", "3D view '%s'" % nm, "(new view)")

    def duplicate_view(self, view, name=None, with_detailing=False):
        from Autodesk.Revit.DB import ViewDuplicateOption
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        src = self._find_view(view)
        opt = ViewDuplicateOption.WithDetailing if with_detailing else ViewDuplicateOption.Duplicate
        if not src.CanViewBeDuplicated(opt):
            raise ActionError("Revit cannot duplicate view %r this way" % fix_plan.el_name(src))
        v = self.doc.GetElement(src.Duplicate(opt))
        nm = self._name_view(v, name, fix_plan.el_name(src) + " Copy (AI)")
        return self._record_new(v, "Views", "duplicate of '%s' (%s, id %d)%s: '%s'" % (fix_plan.el_name(src), src.ViewType, _int(fix_plan.id_int(src.Id)), " with detailing" if with_detailing else "", nm), "(new view)")

    def _view_record(self, v, what, old, new):
        vid = _int(fix_plan.id_int(v.Id))
        self._record((vid, what), {"target_id": vid, "scope": "new element" if vid in self._created else "instance",
                                  "label": "Views", "param_name": what, "old": old, "new": new, "affected": 1})

    def apply_view_template(self, view, template):
        v = self._find_view(view)
        old = fix_plan.el_name(self.doc.GetElement(v.ViewTemplateId)) if fix_plan.id_int(v.ViewTemplateId) > 0 else "none"
        bits = []
        self._template_and_scale(v, template, None, bits)
        self._view_record(v, "(template)", old, _txt(template).strip())
        return True

    def set_view_scale(self, view, scale):
        v = self._find_view(view)
        old = "1:%d" % v.Scale
        bits = []
        self._template_and_scale(v, None, scale, bits)
        self._view_record(v, "(scale)", old, "1:%d" % v.Scale)
        return True

    def place_view_on_sheet(self, view, sheet_number, x=None, y=None):
        from Autodesk.Revit.DB import ViewSheet, Viewport
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        v = self._find_view(view)
        num = _txt(sheet_number).strip()
        sheets = list(FilteredElementCollector(self.doc).OfClass(ViewSheet))
        sh = [s for s in sheets if s.SheetNumber == num]
        if not sh:
            raise ActionError("no sheet numbered %r; sheets: %s" % (num, ", ".join(sorted(s.SheetNumber for s in sheets))[:300]))
        sh = sh[0]
        if not Viewport.CanAddViewToSheet(self.doc, sh.Id, v.Id):
            on = self._view_sheet_map().get(_int(fix_plan.id_int(v.Id)))
            raise ActionError("view %r cannot be placed on sheet %s%s" % (fix_plan.el_name(v), num, (" - it is already on sheet %s (a model view can be on one sheet only)" % on) if on else ""))
        if x is None or y is None:
            o = sh.Outline
            pt = XYZ((o.Min.U + o.Max.U) / 2.0, (o.Min.V + o.Max.V) / 2.0, 0)
        else:
            pt = XYZ(_ft(_num(x, "x")), _ft(_num(y, "y")), 0)
        vp = Viewport.Create(self.doc, sh.Id, v.Id, pt)
        return self._record_new(vp, "Viewports", "view '%s' (%s, id %d) placed on sheet '%s - %s'" % (fix_plan.el_name(v), v.ViewType, _int(fix_plan.id_int(v.Id)), sh.SheetNumber, fix_plan.el_name(sh)), "(view on sheet)")


    # ---- Model health (roadmap feature 3, read-only) ----
    def get_warnings(self, max_groups=50):
        import health_checks
        return health_checks.get_warnings(self.doc, max_groups)

    def find_clashes(self, category_a, category_b, max_elements=300):
        import health_checks
        self.doc.Regenerate()
        return health_checks.find_clashes(self.doc, category_a, category_b, max_elements)

    def room_problems(self):
        import health_checks
        return health_checks.room_problems(self.doc)

    def duplicate_marks(self, category):
        import health_checks
        return health_checks.duplicate_marks(self.doc, category)

    def model_health(self):
        import health_checks
        return health_checks.model_health(self.doc)

    # ---- Rooms (roadmap feature 4) ----
    def _rooms(self, level=None):
        out = []
        for r in FilteredElementCollector(self.doc).OfCategory(BuiltInCategory.OST_Rooms).WhereElementIsNotElementType():
            if level is not None and r.LevelId != level.Id:
                continue
            out.append(r)
        return out

    def _room_info(self, r):
        p = r.get_Parameter(BuiltInParameter.ROOM_NAME)
        loc = r.Location.Point if r.Location is not None else None
        return {"id": _int(fix_plan.id_int(r.Id)), "number": r.Number, "name": p.AsString() if p is not None else None,
                "level": fix_plan.el_name(r.Level) if r.Level is not None else None, "area_m2": round(r.Area * 0.09290304, 2),
                "x": round(loc.X * 0.3048, 3) if loc else None, "y": round(loc.Y * 0.3048, 3) if loc else None}

    def list_rooms(self, level_name=None):
        lv = self._by_name(Level, level_name, "level") if level_name else None
        return sorted([self._room_info(r) for r in self._rooms(lv)], key=lambda x: str(x["number"]))

    def place_room(self, level_name, x, y, name=None, number=None):
        from Autodesk.Revit.DB import UV
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lv = self._by_name(Level, level_name, "level")
        xm, ym = _num(x, "x"), _num(y, "y")
        if max(abs(xm), abs(ym)) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        pt = XYZ(_ft(xm), _ft(ym), lv.Elevation + _ft(1))
        for r in self._rooms(lv):
            if r.Location is not None and r.IsPointInRoom(pt):
                raise ActionError("(%.2f, %.2f) on %s is already inside room %s (id %d); nothing placed" % (xm, ym, fix_plan.el_name(lv), r.Number, _int(fix_plan.id_int(r.Id))))
        num = _txt(number).strip() if number is not None else None
        if num and num in [r.Number for r in self._rooms()]:
            raise ActionError("room number %r is already used" % num)
        room = self.doc.Create.NewRoom(lv, UV(_ft(xm), _ft(ym)))
        self.doc.Regenerate()
        if room.Area <= 0:
            raise ActionError("no enclosed area at (%.2f, %.2f) on %s; nothing placed" % (xm, ym, fix_plan.el_name(lv)))
        if name:
            room.get_Parameter(BuiltInParameter.ROOM_NAME).Set(_txt(name).strip())
        if num:
            room.Number = num
        i = self._room_info(room)
        return self._record_new(room, "Rooms", "room %s '%s' on %s at (%.2f, %.2f) m, area %.2f m2" % (i["number"], i["name"], fix_plan.el_name(lv), xm, ym, i["area_m2"]), "(new room)")

    def place_rooms_in_empty_regions(self, level_name):
        lv = self._by_name(Level, level_name, "level")
        self.doc.Regenerate()
        made = []
        for c in self.doc.get_PlanTopology(lv).Circuits:
            if c.IsRoomLocated:
                continue
            if len(self._created) + len(made) >= MAX_CREATED:
                raise ActionError("more than %d new elements in one action" % MAX_CREATED)
            made.append(self.doc.Create.NewRoom(None, c))
        if not made:
            raise ActionError("every enclosed area on %s already has a room; nothing placed" % fix_plan.el_name(lv))
        self.doc.Regenerate()
        ids = []
        for room in made:
            i = self._room_info(room)
            ids.append(self._record_new(room, "Rooms", "room %s on %s in an enclosed area without a room, area %.2f m2" % (i["number"], fix_plan.el_name(lv), i["area_m2"]), "(new room)"))
        return ids

    def renumber_rooms(self, level_name, start=101, prefix=""):
        lv = self._by_name(Level, level_name, "level")
        rooms = [r for r in self._rooms(lv) if r.Location is not None]
        if not rooms:
            raise ActionError("no placed rooms on %s" % fix_plan.el_name(lv))
        rooms.sort(key=lambda r: (-round(r.Location.Point.Y, 1), round(r.Location.Point.X, 1)))
        s = int(_num(start, "start"))
        pairs = [(r, "%s%d" % (_txt(prefix) if prefix else "", s + i)) for i, r in enumerate(rooms)]
        others = set(x.Number for x in self._rooms() if x.LevelId != lv.Id)
        clash = [v for _, v in pairs if v in others]
        if clash:
            raise ActionError("numbers already used on other levels: %s" % ", ".join(clash))
        orig = [(r, r.Number) for r in rooms]
        for i, r in enumerate(rooms):
            r.Number = "tmp-%d-%d" % (s, i)
        for r, v in pairs:
            r.Number = v
        n = 0
        for (r, old), (_, new) in zip(orig, pairs):
            if old != new:
                rid = _int(fix_plan.id_int(r.Id))
                self._record((rid, "Number"), {"target_id": rid, "scope": "instance", "label": "Rooms", "param_name": "Number",
                                               "old": old, "new": new + " (top to bottom, left to right)", "affected": 1})
                n += 1
        return n

    def tag_rooms(self, view=None):
        from Autodesk.Revit.DB import LinkElementId, UV, ViewType
        v = self.doc.ActiveView if view is None else self._find_view(view)
        if v.ViewType not in (ViewType.FloorPlan, ViewType.CeilingPlan):
            raise ActionError("room tags go in floor or ceiling plans; view %r is a %s" % (fix_plan.el_name(v), v.ViewType))
        lvl = v.GenLevel
        tagged = set()
        for t in FilteredElementCollector(self.doc, v.Id).OfCategory(BuiltInCategory.OST_RoomTags):
            try:
                tagged.add(_int(fix_plan.id_int(t.TaggedLocalRoomId)))
            except Exception:
                pass
        rooms = [r for r in self._rooms(lvl) if r.Location is not None and _int(fix_plan.id_int(r.Id)) not in tagged]
        if not rooms:
            raise ActionError("every placed room on %s is already tagged in view %r" % (fix_plan.el_name(lvl), fix_plan.el_name(v)))
        if len(self._created) + len(rooms) > MAX_CREATED:
            raise ActionError("%d tags would exceed %d new elements in one action" % (len(rooms), MAX_CREATED))
        for r in rooms:
            p = r.Location.Point
            tag = self.doc.Create.NewRoomTag(LinkElementId(r.Id), UV(p.X, p.Y), v.Id)
            self._record_new(tag, "Room Tags", "tag for room %s in view '%s'" % (r.Number, fix_plan.el_name(v)), "(new tag)")
        return len(rooms)


    # ---- PDF export of sheets (roadmap feature 5): recorded in the dry run, written only after Confirm commits ----
    def export_sheets_pdf(self, sheet_numbers, file_name):
        import os, re
        from Autodesk.Revit.DB import ViewSheet
        if not hasattr(self, "_exports"):
            self._exports = []
        sheets = sorted(FilteredElementCollector(self.doc).OfClass(ViewSheet), key=lambda s: s.SheetNumber)
        if _txt(sheet_numbers).strip().lower() == "all":
            pick = list(sheets)
        else:
            want = [_txt(n).strip() for n in (sheet_numbers if isinstance(sheet_numbers, (list, tuple)) else [sheet_numbers])]
            by = dict((s.SheetNumber, s) for s in sheets)
            missing = [n for n in want if n not in by]
            if missing:
                raise ActionError("no sheet numbered %s; sheets: %s" % (", ".join(missing), ", ".join(s.SheetNumber for s in sheets)[:300]))
            pick = [by[n] for n in want]
        if not pick:
            raise ActionError("no sheets to export")
        if len(pick) > 50:
            raise ActionError("at most 50 sheets per export (%d asked)" % len(pick))
        base = _txt(file_name).strip()
        if base.lower().endswith(".pdf"):
            base = base[:-4]
        if not re.match(r"^[A-Za-z0-9 _.\-]{1,80}$", base) or ".." in base or base.startswith("."):
            raise ActionError("file name may use letters, digits, spaces and _ - . only (no folders or paths), up to 80 characters")
        path = os.path.join(EXPORT_DIR, base + ".pdf")
        if os.path.exists(path) or any(f == base for _, f in self._exports):
            i = 2
            while os.path.exists(os.path.join(EXPORT_DIR, "%s-%d.pdf" % (base, i))):
                i += 1
            raise ActionError("%s already exists; a free name is %s-%d (files are never overwritten)" % (path, base, i))
        self._exports.append(([s.Id for s in pick], base))
        sid = _int(fix_plan.id_int(pick[0].Id))
        self._record((sid, "(export pdf)", base), {"target_id": sid, "scope": "export", "label": "PDF Export", "param_name": "(export pdf)",
            "old": "not exported", "new": "export %d sheet(s) (%s) as one PDF to %s - written only after Confirm" % (len(pick), ", ".join(s.SheetNumber for s in pick)[:200], path), "affected": len(pick)})
        return path


    # ---- Openings and shafts (modelling MUST #1) ----
    def create_wall_opening(self, wall_id, distance_m, width_m, height_m, sill_m=0):
        from Autodesk.Revit.DB import Wall, Line
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        from System import Int64
        w = self.doc.GetElement(ElementId(Int64(_int(wall_id))))
        if w is None or not isinstance(w, Wall):
            raise ActionError("element %s is not a wall" % wall_id)
        lc = w.Location.Curve if w.Location is not None else None
        if lc is None or not isinstance(lc, Line):
            raise ActionError("openings are supported in straight walls only")
        dist, wid, hei, sill = _num(distance_m, "distance_m"), _num(width_m, "width_m"), _num(height_m, "height_m"), _num(sill_m, "sill_m")
        if not (0.05 <= wid <= 50 and 0.05 <= hei <= 50 and sill >= 0):
            raise ActionError("width and height must be 0.05-50 m and the sill 0 m or more")
        length = lc.Length * 0.3048
        if dist - wid / 2.0 < 0 or dist + wid / 2.0 > length:
            raise ActionError("a %.2f m wide opening centred at %.2f m does not fit in the wall (length %.2f m)" % (wid, dist, length))
        bb = w.get_BoundingBox(None)
        wall_h = (bb.Max.Z - bb.Min.Z) * 0.3048
        if sill + hei > wall_h + 1e-6:
            raise ActionError("sill %.2f m + height %.2f m is above the wall's height (%.2f m)" % (sill, hei, wall_h))
        p0 = lc.GetEndPoint(0)
        dv = lc.GetEndPoint(1).Subtract(p0).Normalize()
        a = p0.Add(dv.Multiply(_ft(dist - wid / 2.0)))
        b = p0.Add(dv.Multiply(_ft(dist + wid / 2.0)))
        z0 = bb.Min.Z + _ft(sill)
        op = self.doc.Create.NewOpening(w, XYZ(a.X, a.Y, z0), XYZ(b.X, b.Y, z0 + _ft(hei)))
        mark = w.LookupParameter("Mark")
        wn = (mark.AsString() if mark is not None and mark.HasValue else None) or "id %d" % _int(fix_plan.id_int(w.Id))
        return self._record_new(op, "Wall Openings", "opening %.2f x %.2f m in wall %s, centred %.2f m from its start, sill %.2f m" % (wid, hei, wn, dist, sill), "(new opening)")

    def create_shaft(self, bottom_level, top_level, x1, y1, x2, y2):
        from Autodesk.Revit.DB import CurveArray, Line
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lb = self._by_name(Level, bottom_level, "level")
        lt = self._by_name(Level, top_level, "level")
        if lt.Elevation <= lb.Elevation:
            raise ActionError("the top level (%s) must be above the bottom level (%s)" % (fix_plan.el_name(lt), fix_plan.el_name(lb)))
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        xa, xb, ya, yb = min(xs[0], xs[2]), max(xs[0], xs[2]), min(xs[1], xs[3]), max(xs[1], xs[3])
        if not (0.1 <= xb - xa <= 100 and 0.1 <= yb - ya <= 100):
            raise ActionError("a shaft must be 0.1-100 m in each direction")
        z = lb.Elevation
        pts = [XYZ(_ft(xa), _ft(ya), z), XYZ(_ft(xb), _ft(ya), z), XYZ(_ft(xb), _ft(yb), z), XYZ(_ft(xa), _ft(yb), z)]
        prof = CurveArray()
        for i in range(4):
            prof.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
        op = self.doc.Create.NewOpening(lb, lt, prof)
        return self._record_new(op, "Shaft Openings", "shaft %.2f x %.2f m from %s to %s at (%.2f, %.2f)-(%.2f, %.2f) m" % (xb - xa, yb - ya, fix_plan.el_name(lb), fix_plan.el_name(lt), xa, ya, xb, yb), "(new shaft)")


    # ---- Beams and braces (modelling MUST #2) ----
    def _framing_symbol(self, type_name):
        syms = list(FilteredElementCollector(self.doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_StructuralFraming))
        if not syms:
            raise ActionError("no Structural Framing types are loaded in this project (loading families is not supported)")
        want = _txt(type_name).strip()
        full = lambda s: "%s: %s" % (s.FamilyName, fix_plan.el_name(s))
        hits = [s for s in syms if full(s) == want] or [s for s in syms if fix_plan.el_name(s) == want]
        if not hits:
            raise ActionError("no Structural Framing type %r; loaded: %s" % (want, ", ".join(sorted(full(s) for s in syms))[:500]))
        if len(hits) > 1:
            raise ActionError("type name %r is ambiguous: %s; give 'Family: Type'" % (want, ", ".join(full(s) for s in hits)))
        s = hits[0]
        if not s.IsActive:
            s.Activate()
            self.doc.Regenerate()
        return s

    def _framing_line(self, p0, p1):
        from Autodesk.Revit.DB import Line
        length = p0.DistanceTo(p1) * 0.3048
        if not 0.3 <= length <= 100:
            raise ActionError("a beam or brace must be 0.3-100 m long (this one is %.2f m)" % length)
        return Line.CreateBound(p0, p1), length

    def create_beam(self, type_name, level_name, x1, y1, x2, y2):
        from Autodesk.Revit.DB.Structure import StructuralType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        lv = self._by_name(Level, level_name, "level")
        sym = self._framing_symbol(type_name)
        z = lv.Elevation
        line, length = self._framing_line(XYZ(_ft(xs[0]), _ft(xs[1]), z), XYZ(_ft(xs[2]), _ft(xs[3]), z))
        inst = self.doc.Create.NewFamilyInstance(line, sym, lv, StructuralType.Beam)
        return self._record_new(inst, "Structural Framing", "beam '%s: %s' on %s from (%.2f, %.2f) to (%.2f, %.2f) m, length %.2f m" % (sym.FamilyName, fix_plan.el_name(sym), fix_plan.el_name(lv), xs[0], xs[1], xs[2], xs[3], length), "(new beam)")

    def create_brace(self, type_name, base_level, x1, y1, top_level, x2, y2):
        from Autodesk.Revit.DB.Structure import StructuralType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        lb = self._by_name(Level, base_level, "level")
        lt = self._by_name(Level, top_level, "level")
        if lt.Elevation <= lb.Elevation:
            raise ActionError("the top level (%s) must be above the base level (%s)" % (fix_plan.el_name(lt), fix_plan.el_name(lb)))
        sym = self._framing_symbol(type_name)
        line, length = self._framing_line(XYZ(_ft(xs[0]), _ft(xs[1]), lb.Elevation), XYZ(_ft(xs[2]), _ft(xs[3]), lt.Elevation))
        inst = self.doc.Create.NewFamilyInstance(line, sym, lb, StructuralType.Brace)
        return self._record_new(inst, "Structural Framing", "brace '%s: %s' from (%.2f, %.2f) on %s to (%.2f, %.2f) on %s, length %.2f m" % (sym.FamilyName, fix_plan.el_name(sym), xs[0], xs[1], fix_plan.el_name(lb), xs[2], xs[3], fix_plan.el_name(lt), length), "(new brace)")


    # ---- Roofs (modelling MUST #3) ----
    def create_roof(self, level_name, x1, y1, x2, y2, slope_deg=0, roof_type=None, overhang_m=0):
        import math
        from Autodesk.Revit.DB import CurveArray, Line, RoofType, ModelCurveArray
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lv = self._by_name(Level, level_name, "level")
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        sl, ov = _num(slope_deg, "slope_deg"), _num(overhang_m, "overhang_m")
        if not 0 <= sl <= 60:
            raise ActionError("slope must be 0-60 degrees (0 = flat)")
        if not 0 <= ov <= 5:
            raise ActionError("overhang must be 0-5 m")
        xa, xb = min(xs[0], xs[2]) - ov, max(xs[0], xs[2]) + ov
        ya, yb = min(xs[1], xs[3]) - ov, max(xs[1], xs[3]) + ov
        if not (0.5 <= xb - xa <= 200 and 0.5 <= yb - ya <= 200):
            raise ActionError("each side of the roof must be 0.5-200 m (including overhang)")
        types = list(FilteredElementCollector(self.doc).OfClass(RoofType))
        if not types:
            raise ActionError("no roof types are loaded in this project")
        full = lambda t: "%s: %s" % (t.FamilyName, fix_plan.el_name(t))
        if roof_type:
            want = _txt(roof_type).strip()
            hits = [t for t in types if full(t) == want or fix_plan.el_name(t) == want]
            if len(hits) != 1:
                raise ActionError("%s roof type %r; loaded: %s" % ("ambiguous" if hits else "no", want, ", ".join(sorted(full(t) for t in types))[:400]))
            rt = hits[0]
        else:
            basic = [t for t in types if t.FamilyName == "Basic Roof"]
            rt = (basic or types)[0]
        z = lv.Elevation
        pts = [XYZ(_ft(xa), _ft(ya), z), XYZ(_ft(xb), _ft(ya), z), XYZ(_ft(xb), _ft(yb), z), XYZ(_ft(xa), _ft(yb), z)]
        fp = CurveArray()
        for i in range(4):
            fp.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
        import clr
        ref = clr.Reference[ModelCurveArray](ModelCurveArray())   # Revit needs an initialised array (null is rejected)
        res = self.doc.Create.NewFootPrintRoof(fp, lv, rt, ref)
        roof = res[0] if isinstance(res, tuple) else res
        mapping = ref.Value
        if sl > 0:
            if mapping is None or mapping.Size == 0:
                raise ActionError("the roof was made but its edges could not be read, so the slope cannot be set; nothing applied")
            ratio = math.tan(math.radians(sl))
            for i in range(mapping.Size):
                mc = mapping.get_Item(i)
                roof.set_DefinesSlope(mc, True)
                roof.set_SlopeAngle(mc, ratio)
        self.doc.Regenerate()
        shape = "flat" if sl == 0 else "hip, all 4 edges sloped %.1f deg" % sl
        bb = roof.get_BoundingBox(None)
        if bb is not None:
            shape += "; top %.2f m above the level" % ((bb.Max.Z - z) * 0.3048)
        return self._record_new(roof, "Roofs", "roof '%s' on %s, %.2f x %.2f m (%s%s)" % (full(rt), fix_plan.el_name(lv), xb - xa, yb - ya, shape, (", overhang %.2f m" % ov) if ov else ""), "(new roof)")


    # ---- SHOULD features: wall length, ceiling by rectangle, groups ----
    def _el_by_int(self, eid):
        from System import Int64
        return self.doc.GetElement(ElementId(Int64(_int(eid))))

    def change_wall_length(self, wall_id, end, by_m):
        from Autodesk.Revit.DB import Wall, Line, FamilyInstance
        w = self._el_by_int(wall_id)
        if w is None or not isinstance(w, Wall):
            raise ActionError("element %s is not a wall" % wall_id)
        lc = w.Location
        if lc is None or not isinstance(lc.Curve, Line):
            raise ActionError("only straight walls can be extended or shortened")
        e = _txt(end).strip().lower()
        if e not in ("start", "end"):
            raise ActionError("end must be 'start' or 'end'")
        by = _num(by_m, "by_m")
        p0, p1 = lc.Curve.GetEndPoint(0), lc.Curve.GetEndPoint(1)
        dv = p1.Subtract(p0).Normalize()
        L = p0.DistanceTo(p1) * 0.3048
        newL = L + by
        if not 0.3 <= newL <= 1000:
            raise ActionError("the wall would be %.2f m long; it must stay 0.3-1000 m" % newL)
        lo, hi = (-by, L) if e == "start" else (0.0, L + by)
        cut = []
        for fi in FilteredElementCollector(self.doc).OfClass(FamilyInstance):
            try:
                if fi.Host is None or fi.Host.Id != w.Id or fi.Location is None:
                    continue
                t = fi.Location.Point.Subtract(p0).DotProduct(dv) * 0.3048
            except Exception:
                continue
            if t < lo + 0.1 or t > hi - 0.1:
                mk = fi.LookupParameter("Mark")
                cut.append("%s %s (id %d) at %.2f m" % (fi.Category.Name if fi.Category else "element", (mk.AsString() if mk is not None and mk.HasValue else ""), _int(fix_plan.id_int(fi.Id)), t))
        if cut:
            raise ActionError("shortening would cut off: %s; nothing changed" % "; ".join(cut))
        if e == "end":
            lc.Curve = Line.CreateBound(p0, p1.Add(dv.Multiply(_ft(by))))
        else:
            lc.Curve = Line.CreateBound(p0.Subtract(dv.Multiply(_ft(by))), p1)
        self.doc.Regenerate()
        wid = _int(fix_plan.id_int(w.Id))
        mk = w.LookupParameter("Mark")
        self._record((wid, "(length)"), {"target_id": wid, "scope": "instance", "label": "Walls", "param_name": "(length)",
            "old": "%.2f m" % L, "new": "%.2f m (%s moved %+.2f m)" % (newL, e, by), "affected": 1})
        return newL

    def create_ceiling(self, level_name, x1, y1, x2, y2, height_m=2.7, ceiling_type=None):
        from Autodesk.Revit.DB import Ceiling, CeilingType, CurveLoop, Line
        from System.Collections.Generic import List
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        lv = self._by_name(Level, level_name, "level")
        xs = [_num(v, "coordinate") for v in (x1, y1, x2, y2)]
        if max(abs(v) for v in xs) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        h = _num(height_m, "height_m")
        if not 0 <= h <= 20:
            raise ActionError("height must be 0-20 m above the level")
        xa, xb, ya, yb = min(xs[0], xs[2]), max(xs[0], xs[2]), min(xs[1], xs[3]), max(xs[1], xs[3])
        if not (0.5 <= xb - xa <= 200 and 0.5 <= yb - ya <= 200):
            raise ActionError("each side of the ceiling must be 0.5-200 m")
        types = list(FilteredElementCollector(self.doc).OfClass(CeilingType))
        tid = ElementId.InvalidElementId
        if ceiling_type:
            want = _txt(ceiling_type).strip()
            hits = [t for t in types if fix_plan.el_name(t) == want]
            if len(hits) != 1:
                raise ActionError("%s ceiling type %r; loaded: %s" % ("ambiguous" if hits else "no", want, ", ".join(sorted(fix_plan.el_name(t) for t in types))[:400]))
            tid = hits[0].Id
        z = lv.Elevation
        pts = [XYZ(_ft(xa), _ft(ya), z), XYZ(_ft(xb), _ft(ya), z), XYZ(_ft(xb), _ft(yb), z), XYZ(_ft(xa), _ft(yb), z)]
        loop = CurveLoop()
        for i in range(4):
            loop.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
        loops = List[CurveLoop]()
        loops.Add(loop)
        c = Ceiling.Create(self.doc, loops, tid, lv.Id)
        c.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM).Set(_ft(h))
        self.doc.Regenerate()
        tname = fix_plan.el_name(self.doc.GetElement(c.GetTypeId()))
        return self._record_new(c, "Ceilings", "ceiling '%s' on %s at %.2f m, %.2f x %.2f m from (%.2f, %.2f) to (%.2f, %.2f)" % (tname, fix_plan.el_name(lv), h, xb - xa, yb - ya, xa, ya, xb, yb), "(new ceiling)")

    def create_group(self, element_ids, name=None):
        from Autodesk.Revit.DB import GroupType
        from System.Collections.Generic import List
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        ids = element_ids if isinstance(element_ids, (list, tuple)) else [element_ids]
        if not 1 <= len(ids) <= 100:
            raise ActionError("a group needs 1-100 elements")
        els, kinds = [], {}
        for i in ids:
            el = self._el_by_int(i)
            if el is None or el.Category is None:
                raise ActionError("no model element with id %s" % i)
            if fix_plan.id_int(el.GroupId) > 0:
                raise ActionError("element %s is already in a group" % i)
            els.append(el)
            kinds[el.Category.Name] = kinds.get(el.Category.Name, 0) + 1
        lst = List[ElementId]()
        for el in els:
            lst.Add(el.Id)
        g = self.doc.Create.NewGroup(lst)
        taken = set(fix_plan.el_name(t) for t in FilteredElementCollector(self.doc).OfClass(GroupType))
        base = _txt(name).strip() if name else "Group (AI)"
        if name and base in taken:
            raise ActionError("a group named %r already exists" % base)
        nm, k = base, 2
        while nm in taken:
            nm = "%s %d" % (base, k)
            k += 1
        g.GroupType.Name = nm
        self.doc.Regenerate()
        desc = ", ".join("%d %s" % (n, c) for c, n in sorted(kinds.items()))
        return self._record_new(g, "Groups", "group '%s' with %s (grouped elements can no longer be moved one by one)" % (nm, desc), "(new group)")

    def place_group(self, group_name, x, y):
        from Autodesk.Revit.DB import GroupType
        if len(self._created) >= MAX_CREATED:
            raise ActionError("more than %d new elements in one action" % MAX_CREATED)
        xm, ym = _num(x, "x"), _num(y, "y")
        if max(abs(xm), abs(ym)) > MAX_COORD_M:
            raise ActionError("coordinates must be within +/-%d m" % MAX_COORD_M)
        gts = [t for t in FilteredElementCollector(self.doc).OfClass(GroupType) if fix_plan.el_name(t) == _txt(group_name).strip()]
        if not gts:
            raise ActionError("no group named %r; groups: %s" % (group_name, ", ".join(sorted(fix_plan.el_name(t) for t in FilteredElementCollector(self.doc).OfClass(GroupType)))[:300] or "none"))
        g = self.doc.Create.PlaceGroup(XYZ(_ft(xm), _ft(ym), 0), gts[0])
        return self._record_new(g, "Groups", "copy of group '%s' placed at (%.2f, %.2f) m" % (fix_plan.el_name(gts[0]), xm, ym), "(new group)")


    def change_list(self):
        return [dict(self._changes[k]) for k in self._order]

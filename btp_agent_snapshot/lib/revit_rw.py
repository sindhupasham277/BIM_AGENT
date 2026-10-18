# lib/revit_rw.py  (WRITE facade for generated action snippets)
# Records every change it makes. It NEVER starts, commits or rolls back a
# Transaction: the caller (the preview route or write_functions) owns it.
from Autodesk.Revit.DB import StorageType
import fix_plan

MAX_CHANGES = 200

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

    def _element(self, element_id):
        n = _int(element_id)
        el = self.doc.GetElement(fix_plan.make_id(n))
        if el is None:
            raise ActionError("no element with id %s" % n)
        return el

    def get_param(self, element_id, name):
        el = self._element(element_id)
        p, scope, owner = fix_plan.find_param(self.doc, el, name)
        if p is None:
            return None
        return p.AsValueString() or p.AsString() or u""

    def set_param(self, element_id, name, value):
        el = self._element(element_id)
        p, scope, owner = fix_plan.find_param(self.doc, el, name)
        if p is None or p.IsReadOnly or p.StorageType not in fix_plan.SUPPORTED:
            raise ActionError("id %s: '%s' missing, read-only or unsupported" % (_int(element_id), name))
        tid = _int(fix_plan.id_int(owner.Id))
        key = (tid, name)
        if key not in self._changes:
            if len(self._changes) >= MAX_CHANGES:
                raise ActionError("more than %d changes in one action" % MAX_CHANGES)
            affected = 1
            if scope == "type":
                affected = fix_plan.count_instances_of_type(self.doc, el.Category, owner.Id)
            self._changes[key] = {
                "target_id": tid,
                "scope": scope,
                "label": fix_plan.el_name(owner),
                "param_name": name,
                "old": p.AsValueString() or p.AsString() or u"",
                "new": _txt(value),
                "affected": int(affected),
            }
            self._order.append(key)
        else:
            self._changes[key]["new"] = _txt(value)
        if not _set(p, value):
            raise ActionError("Revit refused to set '%s' on id %s" % (name, tid))
        return True

    def change_list(self):
        return [dict(self._changes[k]) for k in self._order]

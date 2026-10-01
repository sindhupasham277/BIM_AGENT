# pyright: reportUndefinedVariable=false
# lib/write_functions.py  (the ONLY file in the project allowed to contain a Transaction)
from Autodesk.Revit.DB import Transaction, TransactionStatus, StorageType, ElementId
import fix_plan

try:
    _STR = basestring  # type: ignore  (IronPython 2.7 only)
except NameError:
    _STR = str              # IronPython 3 / CPython


def _txt(v):
    return v if isinstance(v, _STR) else str(v)


def _norm(s):
    return _txt(s or u"").strip()


def _set(p, value):
    st = p.StorageType
    if st == StorageType.String:
        return p.Set(_txt(value))
    if st == StorageType.Integer:
        return p.Set(int(value))
    if st == StorageType.Double:
        return p.SetValueString(_txt(value))    # parsed in the project's units
    return False


def _set_parameter(doc, args, expected_old):
    plan = fix_plan.plan_set_parameter(doc, args["category"], args["element_ids"],
                                       args["param_name"], args["value"])   # fresh re-plan
    if not plan["ok"]:
        return {"status": "refused", "reason": "; ".join(plan["errors"])}
    for it in plan["items"]:                    # stale check
        key = str(it["target_id"])
        if key not in expected_old or _norm(expected_old[key]) != _norm(it["old"]):
            return {"status": "refused", "reason": "Model changed since the proposal. Nothing applied."}
    t = Transaction(doc, "AI Agent: set " + _txt(args["param_name"]))
    t.Start()
    try:
        for it in plan["items"]:
            owner = doc.GetElement(fix_plan.make_id(it["target_id"]))
            if not _set(owner.LookupParameter(args["param_name"]), args["value"]):
                raise ValueError("could not set id %s" % it["target_id"])
        if t.Commit() != TransactionStatus.Committed:
            return {"status": "failed", "reason": "Revit did not commit"}
    except Exception as ex:
        if t.HasStarted():
            t.RollBack()
        return {"status": "failed", "reason": str(ex)}
    return {"status": "applied", "changed": plan["items"]}


_WRITE_WHITELIST = {"set_parameter": _set_parameter}    # Revit-side whitelist


def apply_fix(doc, function, args, expected_old):
    fn = _WRITE_WHITELIST.get(function)
    if fn is None:
        return {"status": "refused", "reason": "'%s' is not a whitelisted write function" % function}
    return fn(doc, args, expected_old)



# pyright: reportUndefinedVariable=false
# lib/write_functions.py  (the ONLY file in the project allowed to contain a Transaction)
from Autodesk.Revit.DB import Transaction, TransactionStatus, StorageType, ElementId
import fix_plan

try:
    _STR = basestring  # type: ignore  (IronPython 2.7 only)
except NameError:
    _STR = str              # IronPython 3 / CPython


from Autodesk.Revit.DB import IFailuresPreprocessor, FailureProcessingResult, FailureSeverity


class _WarningHandler(IFailuresPreprocessor):
    # Accepts Revit WARNINGS only (records their text); errors are left alone and still roll back.
    __namespace__ = 'BtpAgentWarnings'

    def __init__(self):
        self.warnings = []
        self.errors = []

    def PreprocessFailures(self, failures):
        # warnings: accepted and reported; errors: reported, then a silent rollback (never a modal dialog)
        has_error = False
        for f in failures.GetFailureMessages():
            try:
                text = f.GetDescriptionText()
            except Exception:
                text = '(no description)'
            if f.GetSeverity() == FailureSeverity.Warning:
                if text not in self.warnings:
                    self.warnings.append(text)
                failures.DeleteWarning(f)
            else:
                has_error = True
                if text not in self.errors:
                    self.errors.append(text)
        if has_error:
            o = failures.GetFailureHandlingOptions()
            o.SetClearAfterRollback(True)
            failures.SetFailureHandlingOptions(o)
            return FailureProcessingResult.ProceedWithRollBack
        return FailureProcessingResult.Continue


def _attach_warning_handler(t):
    h = _WarningHandler()
    opts = t.GetFailureHandlingOptions()
    opts.SetFailuresPreprocessor(h)
    opts.SetClearAfterRollback(True)
    t.SetFailureHandlingOptions(opts)
    return h


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
        _wh = _attach_warning_handler(t)
        if t.Commit() != TransactionStatus.Committed:
            return {"status": "failed", "reason": "Revit did not commit" + ((": " + "; ".join(_wh.errors)) if _wh.errors else "")}
    except Exception as ex:
        if t.HasStarted():
            t.RollBack()
        return {"status": "failed", "reason": str(ex)}
    return {"status": "applied", "changed": plan["items"], "warnings": list(_wh.warnings)}


def _action_modules():
    import action_exec
    import revit_rw
    return action_exec, revit_rw


def preview_action(doc, code):
    """DRY RUN: runs the snippet in a Transaction that is ALWAYS rolled back."""
    action_exec, revit_rw = _action_modules()
    rw = revit_rw.RevitRW(doc)
    t = Transaction(doc, "AI Agent: preview (rolled back)")
    t.Start()
    _attach_warning_handler(t)   # no Revit dialog can block a dry run
    try:
        out = action_exec.run_action_code(code, rw)
    finally:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
    return out


def _change_key(c):
    return ("new" if c.get("scope") in ("created", "new element") else c["target_id"], c["param_name"], _norm(c["new"]))


def _run_action(doc, args, expected_old):
    """APPLY: one Transaction; rolled back unless the run matches the preview."""
    action_exec, revit_rw = _action_modules()
    expected = args.get("expected_changes") or []
    rw = revit_rw.RevitRW(doc)
    t = Transaction(doc, "AI Agent: " + _txt(args.get("description", "action"))[:60])
    t.Start()
    try:
        out = action_exec.run_action_code(args.get("code", ""), rw)
        if out["status"] != "ok":
            t.RollBack()
            return {"status": "failed", "reason": "snippet " + out["status"] + ": " + _txt(out.get("message", ""))}
        changes = out["changes"]
        for c in changes:
            if c.get("scope") in ("created", "new element"):
                continue
            key = "%s|%s" % (c["target_id"], c["param_name"])
            if key not in expected_old or _norm(expected_old[key]) != _norm(c["old"]):
                t.RollBack()
                return {"status": "refused", "reason": "Model changed since the preview. Nothing applied."}
        if sorted(_change_key(c) for c in changes) != sorted(_change_key(c) for c in expected):
            t.RollBack()
            return {"status": "refused", "reason": "The action did something different from the preview. Nothing applied."}
        _wh = _attach_warning_handler(t)
        if t.Commit() != TransactionStatus.Committed:
            return {"status": "failed", "reason": "Revit did not commit" + ((": " + "; ".join(_wh.errors)) if _wh.errors else "")}
    except Exception as ex:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        return {"status": "failed", "reason": str(ex)}
    return {"status": "applied", "changed": changes, "warnings": list(_wh.warnings)}


def temporary_view(doc, view, ids, mode):
    """Family 5, DISPLAY ONLY: temporary hide/isolate/reset in the active view (not saved with the model).
    Revit requires a Transaction even for these, so it lives here. NOT on the apply whitelist."""
    from Autodesk.Revit.DB import TemporaryViewMode
    if mode not in ("isolate", "hide", "reset"):
        raise ValueError("mode must be isolate, hide or reset")
    t = Transaction(doc, "AI Agent: temporary " + mode)
    t.Start()
    try:
        if mode == "isolate":
            view.IsolateElementsTemporary(ids)
        elif mode == "hide":
            view.HideElementsTemporary(ids)
        else:
            view.DisableTemporaryViewMode(TemporaryViewMode.TemporaryHideIsolate)
        if t.Commit() != TransactionStatus.Committed:
            raise RuntimeError("Revit did not commit the temporary view change")
    except Exception:
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        raise


_WRITE_WHITELIST = {"set_parameter": _set_parameter, "run_action": _run_action}    # Revit-side whitelist


def apply_fix(doc, function, args, expected_old):
    fn = _WRITE_WHITELIST.get(function)
    if fn is None:
        return {"status": "refused", "reason": "'%s' is not a whitelisted write function" % function}
    return fn(doc, args, expected_old)



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


def _do_export(doc, entry, folder):
    """Runs ONLY after a committed Confirm (never in a dry run). Writes into the approved folder only, never overwriting."""
    import os
    from Autodesk.Revit.DB import ElementId
    from System.Collections.Generic import List
    kind, base, ids = entry["kind"], entry["base"], entry.get("ids") or []
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
        before = set(os.listdir(folder))
        if any(f.lower().startswith(base.lower()) for f in before):
            return "Export NOT written: a file starting with %s already exists in %s (files are never overwritten)" % (base, folder)
        lst = List[ElementId]()
        for i in ids:
            lst.Add(i)
        ok = None
        if kind == "pdf":
            from Autodesk.Revit.DB import PDFExportOptions
            o = PDFExportOptions()
            o.FileName = base
            o.Combine = True
            ok = doc.Export(folder, lst, o)
        elif kind == "dwg":
            from Autodesk.Revit.DB import DWGExportOptions
            ok = doc.Export(folder, base, lst, DWGExportOptions())
        elif kind in ("png", "jpg"):
            from Autodesk.Revit.DB import ImageExportOptions, ExportRange, ImageFileType, ImageResolution, ZoomFitType
            o = ImageExportOptions()
            o.ExportRange = ExportRange.SetOfViews
            o.SetViewsAndSheets(lst)
            o.FilePath = os.path.join(folder, base)
            ft = ImageFileType.PNG if kind == "png" else ImageFileType.JPEGLossless
            o.HLRandWFViewsFileType = ft
            o.ShadowViewsFileType = ft
            o.ImageResolution = ImageResolution.DPI_150
            o.ZoomType = ZoomFitType.FitToPage
            o.PixelSize = 2000
            doc.ExportImage(o)
            ok = True
        elif kind == "ifc":
            from Autodesk.Revit.DB import IFCExportOptions, Transaction
            t = Transaction(doc, "AI Agent: IFC export (rolled back)")
            t.Start()
            try:
                ok = doc.Export(folder, base, IFCExportOptions())
            finally:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
        elif kind == "nwc":
            from Autodesk.Revit.DB import NavisworksExportOptions
            ok = doc.Export(folder, base, NavisworksExportOptions())
        new = sorted(f for f in os.listdir(folder) if f not in before and f.lower().startswith(base.lower()))
        if new:
            return "Export written (%s): %s in %s" % (kind.upper(), ", ".join(new[:10]) + (" ..." if len(new) > 10 else ""), folder)
        return "Export problem (%s): Revit returned %s but no file starting with %s was created" % (kind.upper(), ok, base)
    except Exception as ex:
        return "Export FAILED (%s): %s" % (kind.upper(), ex)


def _do_pdf_export(doc, ids, base, folder):
    """Runs ONLY after a committed Confirm (never in a dry run). Writes one combined PDF into the approved folder."""
    import os
    from Autodesk.Revit.DB import PDFExportOptions, ElementId
    from System.Collections.Generic import List
    path = os.path.join(folder, base + ".pdf")
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
        if os.path.exists(path):
            return "PDF NOT written: %s already exists (files are never overwritten)" % path
        opts = PDFExportOptions()
        opts.FileName = base
        opts.Combine = True
        lst = List[ElementId]()
        for i in ids:
            lst.Add(i)
        ok = doc.Export(folder, lst, opts)
        if ok and os.path.exists(path):
            return "PDF written: %s (%d sheet(s))" % (path, len(ids))
        return "PDF export problem: Revit returned %s and the file %s" % (ok, "exists" if os.path.exists(path) else "was not created")
    except Exception as ex:
        return "PDF export FAILED: %s" % ex


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
    notes = list(_wh.warnings)
    for entry in getattr(rw, "_exports", []):   # exports happen only here, after the commit
        if isinstance(entry, dict):
            notes.append(_do_export(doc, entry, revit_rw.EXPORT_DIR))
        else:
            ids, base = entry
            notes.append(_do_pdf_export(doc, ids, base, revit_rw.EXPORT_DIR))
    return {"status": "applied", "changed": changes, "warnings": notes}


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



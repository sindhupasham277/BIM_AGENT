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
    return _verified(doc, {"status": "applied", "changed": plan["items"], "warnings": list(_wh.warnings)}, args["param_name"])


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
    if out.get("status") == "ok" and getattr(rw, "_stairs", None):   # stairs: trial build in their own scope, then cancelled
        if len(out.get("changes", [])) > 1:   # stairs are their own undo step, so they must be alone on a card
            return {"status": "error", "message": "stairs must be on a card of their own (they are a separate undo step); make the stairs alone first, then ask for the other changes in a separate request", "changes": out.get("changes", [])}
        checks = []
        for req in rw._stairs:
            try:
                info = _build_stairs(doc, req, True)
            except Exception as ex:
                info = {"error": str(ex)}
            if info.get("error"):
                return {"status": "error", "message": "stairs check failed: " + info["error"], "changes": out.get("changes", [])}
            checks.append(info["summary"])
        out["result"] = {"snippet_result": out.get("result"), "stairs_check": checks}
    return out


def _not_kept(doc, changes, param_name=None):
    """After the commit: parameter changes whose value still equals the old value (Revit did not keep them)."""
    bad = []
    for c in changes:
        name = c.get("param_name") or param_name
        if c.get("scope") not in ("instance", "type") or not name:
            continue
        try:
            el = doc.GetElement(fix_plan.make_id(c["target_id"]))
            p = el.LookupParameter(name) if el is not None else None
            if p is None:
                continue
            now = p.AsValueString() or p.AsString() or u""
        except Exception:
            continue
        if _norm(now) == _norm(c.get("old")) and _norm(c.get("old")) != _norm(c.get("new")):
            bad.append("%s on id %s" % (name, c["target_id"]))
    return bad


def _verified(doc, result, param_name=None):
    """Applied results are checked against the model; values Revit did not keep are reported, never hidden."""
    if result.get("status") != "applied":
        return result
    bad = _not_kept(doc, result.get("changed") or [], param_name)
    if bad and len(bad) == len([c for c in result.get("changed") or [] if c.get("scope") in ("instance", "type")]):
        return {"status": "failed", "reason": "Revit did not keep the new values (" + "; ".join(bad)[:300] + "). Press Ctrl+Z to remove the empty step."}
    if bad:
        result = dict(result, warnings=list(result.get("warnings") or []) + ["Not kept by Revit: " + "; ".join(bad)[:300]])
    return result


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


def _build_stairs(doc, req, trial):
    """trial=True: build inside a StairsEditScope and cancel (preview check); trial=False: build and commit (after Confirm)."""
    from Autodesk.Revit.DB import Line, XYZ, ElementId
    from Autodesk.Revit.DB import StairsEditScope
    from Autodesk.Revit.DB.Architecture import StairsRun, StairsRunJustification
    from System import Int64
    base, top = doc.GetElement(ElementId(Int64(req["base"]))), doc.GetElement(ElementId(Int64(req["top"])))
    scope = StairsEditScope(doc, "AI Agent: stairs" + (" (check)" if trial else ""))
    t = None
    try:
        sid = scope.Start(base.Id, top.Id)
        t = Transaction(doc, "AI Agent: stairs run")
        t.Start()
        h = _attach_warning_handler(t)
        st = doc.GetElement(sid)
        want = st.DesiredRisersNumber
        tread = st.ActualTreadDepth
        p0 = XYZ(req["x1"], req["y1"], base.Elevation)
        dv = XYZ(req["dx"], req["dy"], 0)
        run, used = None, 0
        for k in (want - 1, want, want + 1):
            if k < 2:
                continue
            r = StairsRun.CreateStraightRun(doc, sid, Line.CreateBound(p0, p0.Add(dv.Multiply(k * tread))), StairsRunJustification.Center)
            doc.Regenerate()
            if doc.GetElement(sid).ActualRisersNumber == want:
                run, used = r, k
                break
            doc.Delete(r.Id)
        if run is None:
            raise Exception("could not fit the %d risers needed in one straight run" % want)
        run.ActualRunWidth = req["width"]
        if t.Commit() != TransactionStatus.Committed:
            raise Exception("Revit did not commit the stairs run" + ((": " + "; ".join(h.errors)) if getattr(h, "errors", None) else ""))
        st = doc.GetElement(sid)
        x1, y1, x2, y2, w = req["txt"]
        end = p0.Add(dv.Multiply(used * tread))
        summary = "straight stairs %s to %s: %d risers of %.0f mm, treads %.0f mm, run %.2f m from (%.2f, %.2f) to (%.2f, %.2f) m, width %.2f m" % (
            base.Name, top.Name, st.ActualRisersNumber, st.ActualRiserHeight * 304.8, st.ActualTreadDepth * 304.8,
            used * tread * 0.3048, x1, y1, end.X * 0.3048, end.Y * 0.3048, w)
        if trial:
            scope.Cancel()
        else:
            scope.Commit(h)
        return {"summary": summary}
    except Exception as ex:
        try:
            if t is not None and t.HasStarted() and not t.HasEnded():
                t.RollBack()
        except Exception:
            pass
        try:
            if scope.IsActive:
                scope.Cancel()
        except Exception:
            pass
        return {"error": str(ex)}


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
    for req in getattr(rw, "_stairs", []):   # stairs: built after the commit, in their own stairs scope (own undo step)
        try:
            info = _build_stairs(doc, req, False)
        except Exception as ex:
            info = {"error": str(ex)}
        notes.append(("Stairs FAILED: " + info["error"]) if info.get("error") else ("Stairs created: " + info["summary"]))
    return _verified(doc, {"status": "applied", "changed": changes, "warnings": notes})


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



# pyright: reportMissingImports=false, reportUndefinedVariable=false
# lib/fix_handler.py  (the ONLY non-test importer of write_functions)
# Works on IronPython 2.7 and CPython 3.
import io
import time
import traceback
import clr
clr.AddReference("RevitAPIUI")
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
import write_functions

try:
    _U = unicode            # Python 2
except NameError:
    _U = str                # Python 3

_KEEP = []   # keeps handler + event alive (garbage collection)
LOG_PATH = r"C:\Users\sindh\OneDrive\Desktop\BTP\BIM_AGENT\logs\fix_handler_log.txt"
LOG_ERROR = []


def _to_text(v):
    if isinstance(v, _U):
        return v
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    return _U(v)


def write_text(path, text, mode="w"):
    with io.open(path, mode, encoding="utf-8") as f:
        f.write(_to_text(text))


def log(text):
    try:
        write_text(LOG_PATH, time.strftime("%H:%M:%S ") + _to_text(text) + u"\n", "a")
    except Exception as ex:
        LOG_ERROR.append(repr(ex))


class ApplyFixHandler(IExternalEventHandler):
    __namespace__ = "BtpAgentFixHandler"

    def __init__(self, on_done):
        self.request = None      # {"function":..., "args":..., "expected_old":...}
        self.on_done = on_done

    def Execute(self, uiapp):
        log("Execute ENTERED")
        r = self.request
        self.request = None
        try:
            if r is None:
                result = {"status": "failed", "reason": "no request set"}
            else:
                doc = uiapp.ActiveUIDocument.Document
                result = write_functions.apply_fix(doc, r["function"], r["args"], r["expected_old"])
        except Exception as ex:
            log("apply_fix raised: " + traceback.format_exc())
            result = {"status": "failed", "reason": str(ex)}
        log("result status = " + str(result.get("status")))
        try:
            self.on_done(result)     # must be quick. NO network calls in here.
            log("on_done finished")
        except Exception:
            log("on_done raised: " + traceback.format_exc())

    def GetName(self):
        return "AIAgent.ApplyFix"


def create_apply_event(on_done):
    """Call ONCE from a valid API context (the pushbutton script, before the window opens)."""
    handler = ApplyFixHandler(on_done)
    event = ExternalEvent.Create(handler)
    _KEEP.append((handler, event))
    log("event created")
    return handler, event

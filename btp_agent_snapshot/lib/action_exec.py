# lib/action_exec.py  (runs a generated ACTION snippet against revit_rw)
# Same static validator, safe builtins, timeout and plain-result rule as the
# read-only sandbox (reused from sandbox_exec). It NEVER touches a Transaction:
# the caller owns it and decides whether to roll back or commit.
import sys
import time

PANEL = r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions\btp_agent.extension\BTP.tab\Agent.panel"
if PANEL not in sys.path:
    sys.path.append(PANEL)
import sandbox_exec

ACTION_METHODS = ("get_param", "set_param", "list_levels", "list_wall_types", "create_wall", "list_types", "change_type")


def run_action_code(code, rw, timeout_sec=5):
    try:
        sandbox_exec.validate_snippet(code)
    except sandbox_exec.SandboxRejected as e:
        return {"status": "rejected", "message": str(e), "changes": []}

    deadline = [time.time() + timeout_sec]

    def safe_range(*args):
        for i in range(*args):
            if time.time() > deadline[0]:
                raise sandbox_exec.SandboxTimeout("Snippet exceeded {}s timeout".format(timeout_sec))
            yield i

    builtins = dict(sandbox_exec.SAFE_BUILTINS)
    builtins["range"] = safe_range
    # Action snippets only (the read-only sandbox is unchanged):
    builtins["str"] = str
    builtins["int"] = int
    builtins["float"] = float

    facade = sandbox_exec._Facade()
    for name in ACTION_METHODS:
        setattr(facade, name, sandbox_exec._wrap(getattr(rw, name)))

    namespace = {"__builtins__": builtins, "revit_rw": facade, "result": None}

    try:
        exec(compile(code, "<action>", "exec"), namespace)
    except sandbox_exec.SandboxTimeout as e:
        return {"status": "timeout", "message": str(e), "changes": rw.change_list()}
    except Exception as e:
        return {"status": "error", "message": str(e), "changes": rw.change_list()}

    try:
        plain = sandbox_exec._plain(namespace.get("result"))
    except ValueError as e:
        return {"status": "error", "message": str(e), "changes": rw.change_list()}

    return {"status": "ok", "result": plain, "changes": rw.change_list()}

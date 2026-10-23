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

ACTION_METHODS = ("get_param", "set_param", "list_levels", "list_wall_types", "create_wall", "list_types", "change_type", "move_element", "copy_element", "delete_elements", "get_location", "list_family_types", "place_door", "place_window", "get_line", "rotate_element", "mirror_element", "place_instance", "create_level", "create_grid", "create_floor_in_room", "create_floor", "create_ceiling_in_room", "list_floor_types", "list_ceiling_types", "unjoin_wall", "allow_wall_joins", "join_geometry", "unjoin_geometry", "tag_elements", "add_text_note", "create_sheet", "list_sheets", "get_elements", "get_wall_joins", "unjoin_walls", "list_schedulable_fields", "list_schedules", "read_schedule", "create_schedule", "add_schedule_field", "remove_schedule_field", "set_schedule_sort", "set_schedule_filter", "place_schedule_on_sheet", "list_views", "list_view_templates", "list_title_blocks", "create_plan_view", "create_section", "create_3d_view", "duplicate_view", "apply_view_template", "set_view_scale", "place_view_on_sheet", "get_warnings", "find_clashes", "room_problems", "duplicate_marks", "model_health", "list_rooms", "place_room", "place_rooms_in_empty_regions", "renumber_rooms", "tag_rooms", "export_sheets_pdf", "create_wall_opening", "create_shaft", "create_beam", "create_brace", "create_roof")


def _hint(msg):   # C16: say how to fix common snippet mistakes
    if "is not defined" in msg:
        return msg + " (call helper methods as revit_rw.<method>(...); the only builtins are len, range, enumerate, sum, min, max, sorted, abs, round, any, all, str, int, float)"
    if "_Facade" in msg and "has no attribute" in msg:
        return msg + " (that method does not exist on revit_rw; use the methods listed in the rules)"
    return msg


def run_action_code(code, rw, timeout_sec=5):
    try:
        sandbox_exec.validate_snippet(code)
    except sandbox_exec.SandboxRejected as e:
        return {"status": "rejected", "message": str(e), "changes": []}

    deadline = [time.time() + timeout_sec]

    def safe_range(*args):
        r = sandbox_exec._LAZY_RANGE(*args)
        if len(r) > sandbox_exec.MAX_RANGE_ITEMS:
            raise ValueError('range is too large (max %d items)' % sandbox_exec.MAX_RANGE_ITEMS)
        for i in r:
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
        return {"status": "error", "message": _hint(str(e)), "changes": rw.change_list()}

    try:
        plain = sandbox_exec._plain(namespace.get("result"))
    except ValueError as e:
        return {"status": "error", "message": str(e), "changes": rw.change_list()}

    return {"status": "ok", "result": plain, "changes": rw.change_list()}

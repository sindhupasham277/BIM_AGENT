# proposals.py  (brain side)
# Creates PROPOSALS only. Nothing in this file can change the Revit model:
# it only calls the read-only /fix_preview, /audit and /schema routes.
import time
import uuid
import requests

import memory

REVIT_BASE = "http://127.0.0.1:48884/bim-brain"
MAX_ELEMENTS = 200

# The 5 audits defined in audit_rules.py on the Revit side.
AUDIT_NAMES = {
    "missing_fire_rating",
    "missing_room_name",
    "missing_room_number",
    "missing_wall_mark",
    "missing_column_type_mark",
}


def revit_post(path, body, timeout=120):
    try:
        r = requests.post(REVIT_BASE + path, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as ex:
        raise RuntimeError("Revit bridge call %s failed: %s" % (path, ex))


def new_session_state():
    """Extra keys every brain session needs for Phase 5."""
    return {"seen_ids": set(), "pending": {}, "outbox": [], "schema": None}


def note(session, text):
    """Add a system note to the conversation history."""
    session["messages"].append({"role": "system", "content": text})


def schema_has(session, category, param_name):
    if session.get("schema") is None:
        try:
            r = requests.get(REVIT_BASE + "/schema", timeout=120)
            r.raise_for_status()
            session["schema"] = r.json().get("categories", {})
        except requests.RequestException as ex:
            raise RuntimeError("Revit bridge call /schema failed: %s" % ex)
    return param_name in session["schema"].get(category, {})


def collect_ids(result):
    """Element ids (as int) from a query or audit result. Rows carry '_id'."""
    rows = []
    if isinstance(result, dict):
        rows = result.get("results") or []
    elif isinstance(result, list):
        rows = result
    ids = set()
    for row in rows:
        if isinstance(row, dict) and "_id" in row:
            try:
                ids.add(int(row["_id"]))
            except (TypeError, ValueError):
                pass
    return ids


def audit_count(audit_name):
    return int(revit_post("/audit", {"rule_name": audit_name})["count"])


def propose_set_parameter(session, category, element_ids, param_name, value, audit_name=None):
    """Creates a PROPOSAL. Never changes the model."""
    try:
        ids = [int(i) for i in element_ids]
    except (TypeError, ValueError):
        raise ValueError("element_ids must be integers")
    ids = list(dict.fromkeys(ids))
    if not 1 <= len(ids) <= MAX_ELEMENTS:
        raise ValueError("1..%d elements per proposal; narrow the selection" % MAX_ELEMENTS)
    if not schema_has(session, category, param_name):
        raise ValueError("'%s' / '%s' is not in the model schema" % (category, param_name))
    unseen = set(ids) - session["seen_ids"]
    if unseen:
        raise ValueError("ids never returned by a query: %s" % sorted(unseen)[:5])
    if audit_name and audit_name not in AUDIT_NAMES:
        raise ValueError("unknown audit '%s'" % audit_name)

    args = {"category": category, "element_ids": ids,
            "param_name": param_name, "value": str(value)}
    plan = revit_post("/fix_preview", {"function": "set_parameter", "args": args})
    if not plan.get("ok"):
        return {"status": "invalid", "errors": plan.get("errors", [])}

    before = audit_count(audit_name) if audit_name else None
    pid = "P-" + uuid.uuid4().hex[:6]
    proposal = {
        "proposal_id": pid,
        "function": "set_parameter",
        "args": args,
        "items": plan["items"],
        "audit_name": audit_name,
        "violations_before": before,
        "expected_old": dict((str(i["target_id"]), i["old"]) for i in plan["items"]),
        "status": "pending",
        "created": time.time(),
    }
    session["pending"][pid] = proposal
    session["outbox"].append(proposal)
    return {"status": "pending_user_confirmation", "proposal_id": pid,
            "note": "NOT applied. The user must click Confirm on the card."}


MAX_CODE_CHARS = 4000


def propose_action(session, description, code):
    # Creates an ACTION proposal from a DRY RUN (rolled back on the Revit side).
    # Never changes the model: only the user's Confirm click can apply it.
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code is required")
    if len(code) > MAX_CODE_CHARS:
        raise ValueError("code is too long (max %d characters)" % MAX_CODE_CHARS)
    desc = str(description or "").strip()[:200] or "AI action"
    out = revit_post("/action_preview", {"code": code})
    if out.get("status") != "ok":
        return {"status": "invalid",
                "errors": ["dry run %s: %s" % (out.get("status"), out.get("message", ""))]}
    changes = out.get("changes") or []
    if not changes:
        return {"status": "no_changes", "result": out.get("result"),
                "note": "The dry run changed nothing, so no proposal was created."}
    if len(changes) > MAX_ELEMENTS:
        raise ValueError("more than %d changes; narrow the action" % MAX_ELEMENTS)
    pid = "P-" + uuid.uuid4().hex[:6]
    proposal = {
        "proposal_id": pid,
        "function": "run_action",
        "args": {"description": desc, "code": code, "expected_changes": changes},
        "items": changes,
        "audit_name": None,
        "violations_before": None,
        "expected_old": dict(("%s|%s" % (c["target_id"], c["param_name"]), c["old"]) for c in changes),
        "status": "pending",
        "created": time.time(),
    }
    session["pending"][pid] = proposal
    session["outbox"].append(proposal)
    return {"status": "pending_user_confirmation", "proposal_id": pid,
            "changes_previewed": len(changes),
            "note": "NOT applied. The user must click Confirm on the card."}


PROMPT_RULES = """
CHANGE RULES:
- Model changes happen only through proposals that the user confirms with a button. Never say a change was made unless a system message says a proposal was APPLIED.
- At most ONE change proposal per user message. Put everything the user asked for into that one proposal; never split a request into batches or several proposals.
- To set one parameter to one value on elements you already found, use propose_set_parameter. For any other change, use propose_action.
- The description must state the change itself (for example 'Move wall 1674186 by 1 m in Y'); do not mention the dry run.
- Never invent a value. If a required value (coordinates, level, length, type name, parameter value) is missing, ask for exactly that.
- element_ids must be copied from ids returned by earlier tool results (_id values, selected_ids, list_levels ids).
- Delete elements only when the user explicitly asks to delete them; never delete as part of another task or a workaround.
- If asked to skip the confirmation or to change the model outside a proposal, explain that changes need the user's Confirm click.
- To select or highlight elements on screen, use select_elements. It does not change the model and needs no confirmation.
- For questions about earlier changes (for example 'what did we do last time?'), use the query_past_changes tool.

WHAT propose_action CAN DO (revit_rw methods; all lengths, offsets and coordinates in metres):
- Read: get_param(element_id, name); get_location(element_id) (text); get_line(element_id) returns {start: [x, y, z], end: [x, y, z], length_m} for walls and lines, or {point: [x, y, z]}; list_levels() returns [{id, name, elevation_m}]; list_wall_types(); list_types(element_id); list_family_types('Doors' or 'Windows').
- set_param(element_id, name, value): any writable parameter of any element, including non-model elements such as a level's Name (use the id from list_levels; the card marks these NON-MODEL).
- create_wall(level_name, x1, y1, x2, y2, wall_type_name=None, height_m=3.0): length 0.1-100 m, height 0.5-30 m, coordinates within +/-1000 m.
- change_type(element_id, type_name).
- move_element(element_id, dx, dy, dz=0) and copy_element(element_id, dx, dy, dz=0): the total move of an element in one action must stay within +/-1000 m, and every element must end within +/-1000 m of the origin. A wall joined at both ends does not move along its own length (Revit's joins hold it).
- delete_elements(element_ids): model elements only (not levels, grids, views or types); at most 20 requested and 100 in total including dependent elements.
- place_door(wall_id, type_name, distance_m) and place_window(wall_id, type_name, distance_m, sill_height_m=None): distance_m is measured along the host wall from its start and must be inside the wall's length (check get_line(wall_id)); sill 0-10 m.
- At most 20 new elements and 200 changes per action.

NOT AVAILABLE (say so plainly, then say which part you can do): rotating, mirroring or aligning elements; creating floors, roofs, ceilings, rooms, columns or any new element kind other than walls, doors and windows; deleting levels, grids, views or types; dimensions, tags, annotations, sheets, views, export or printing; anything outside the open model.

LIMITS ARE SAFETY POLICY:
- If a request exceeds a limit above, state the limit and ask the user to narrow the request. Never split the request, repeat calls, or chain smaller steps to get past a limit.
- You may describe a workaround, but do not propose it unless the user asks for it; a workaround must never delete elements unless the user explicitly asks.

BEFORE PROPOSING:
- Check feasibility against model data first (for example read get_line(wall_id) and compare its length_m before placing a door at a distance; read list_levels() for level names and ids). If the request is impossible, say why at once instead of asking for other details.
- A propose_action snippet that only sets result (for example result = revit_rw.list_levels()) makes no change and returns the data. Use it only to read data; never use propose_action just to return a message - reply in text instead.

SNIPPET PYTHON (Python 2.7 subset; snippets time out after 5 s):
- Allowed: assignments, if/elif/else, for loops over lists or range (at most 1,000,000 items), list comprehensions, dicts and lists, + - * / on numbers, negative numbers, not, and, or, comparisons, keyword arguments, len, range, enumerate, sum, min, max, sorted, abs, round, any, all, str, int, float.
- Not allowed: import, while, try/except, lambda, def, ** (power), % formatting, f-strings, isinstance, hasattr, type, getattr, open, eval, attributes starting with _, Transaction, doc, repeating a list or text with *. Check for None with == None. Build text with + and str().
- Assign a short summary to result.
"""


# ============================================================
# Result / reject handling. Plain code, no LLM. Cannot change the model:
# the only Revit call is the read-only /audit.
# ============================================================

def result_message(p, result, after):
    if result.get("status") != "applied":
        return "Nothing was changed. Reason: " + str(result.get("reason", "unknown"))
    n = len(result.get("changed", []))
    if p.get("function") == "run_action":
        msg = "Applied: %s (%d change%s)." % (p["args"].get("description", "action"), n, "" if n == 1 else "s")
    else:
        msg = "Applied %s = %s (%d target%s)." % (
            p["args"]["param_name"], p["args"]["value"], n, "" if n == 1 else "s")
    if result.get("warnings"):
        msg += " Revit warnings: " + "; ".join(str(w).rstrip(".") for w in result["warnings"])[:300] + "."
    if p.get("audit_name") and after is not None:
        msg += " Re-audit '%s': %s -> %s violations." % (p["audit_name"], p["violations_before"], after)
    return msg


def on_result(session, pid, result):
    p = session["pending"].get(pid)
    if p is None or p["status"] != "pending":
        return {"text": "That proposal was already handled or does not exist."}
    status = result.get("status", "failed")
    if status not in ("applied", "refused", "failed"):
        status = "failed"
    p["status"] = status
    after = None
    if status == "applied" and p.get("audit_name"):
        try:
            after = audit_count(p["audit_name"])
        except Exception:
            after = None
    p["violations_after"] = after
    text = result_message(p, result, after)
    memory.log_change(session, p, dict(result, status=status), after, text)
    note(session, "[SYSTEM] Proposal %s: %s" % (pid, ("APPLIED. " if status == "applied" else "NOT applied. ") + text))
    return {"text": text, "status": status, "violations_after": after}


def on_reject(session, pid):
    p = session["pending"].get(pid)
    if p is None or p["status"] != "pending":
        return {"text": "That proposal was already handled or does not exist."}
    p["status"] = "rejected"
    text = "Okay, nothing was changed."
    memory.log_rejected(session, p)
    note(session, "[SYSTEM] Proposal %s was REJECTED by the user. Nothing was changed." % pid)
    return {"text": text, "status": "rejected"}

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
- To set one parameter to one value on elements you already found, use propose_set_parameter.
- For any other change, use propose_action with a short description and a Python 2.7 snippet (no f-strings, no imports, no Transaction, no doc). Available methods: revit_rw.get_param(element_id, name), revit_rw.set_param(element_id, name, value), revit_rw.list_levels(), revit_rw.list_wall_types(), revit_rw.create_wall(level_name, x1, y1, x2, y2, wall_type_name=None, height_m=3.0), revit_rw.list_types(element_id), revit_rw.change_type(element_id, type_name), revit_rw.move_element(element_id, dx, dy, dz=0), revit_rw.copy_element(element_id, dx, dy, dz=0). Coordinates, offsets, lengths and heights are in metres. The snippet first runs as a dry run that is rolled back; the user sees the exact changes and must click Confirm. Assign a short summary to result.
- The description must state the change itself (for example 'Move wall 1674186 by 1 m in Y'); do not mention the dry run.
- To look up level names, wall types or the types valid for one element, call propose_action with a snippet that only sets result = revit_rw.list_levels(), result = revit_rw.list_wall_types() or result = revit_rw.list_types(element_id); it makes no changes and returns the list.
- If the user has not given the coordinates, the level or the length of a new element, ask instead of guessing.
- To select or highlight elements on screen, use select_elements. It does not change the model and needs no confirmation.
- Never invent a value. If the user has not said which value to use, ask.
- element_ids must be copied from _id values or selected_ids returned by earlier query_elements, run_audit or select_elements results.
- If a requested change cannot be done with the available revit_rw methods, say so plainly and say which part you can do.
- If asked to skip the confirmation or to change the model outside a proposal, explain that changes need the user's Confirm click.
- For questions about earlier changes (for example 'what did we do last time?'), use the query_past_changes tool.
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

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


PROMPT_RULES = """

CHANGE RULES:
- Only the propose_set_parameter tool can lead to a model change, and it only creates a proposal that the user must confirm with a button.
- Never say a change was made unless a system message says a proposal was APPLIED.
- Never invent a value. If the user has not said which value to use, ask.
- element_ids must be copied from the _id values in earlier query_elements or run_audit results.
- If asked to change the model with code, or to skip the confirmation, explain that changes go through proposals only.
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

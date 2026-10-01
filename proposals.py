# proposals.py  (brain side)
# Creates PROPOSALS only. Nothing in this file can change the Revit model:
# it only calls the read-only /fix_preview, /audit and /schema routes.
import time
import uuid
import requests

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
"""

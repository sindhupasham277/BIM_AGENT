import os
import json
import re

from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import requests

import time

import memory
import proposals


# ============================================================
# FastAPI app
# ============================================================

app = FastAPI()

client = OpenAI(api_key=os.environ["BTP_API"])


# ============================================================
# Load tool schemas
# ============================================================

with open("tool_schemas.json", "r") as f:
    TOOL_SCHEMAS = json.load(f)


OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"]
        }
    }
    for tool in TOOL_SCHEMAS.values()
]


# ============================================================
# Request model
# ============================================================

class ResultPayload(BaseModel):
    session_id: str
    result: dict


class RejectPayload(BaseModel):
    session_id: str


class MessagePayload(BaseModel):
    session_id: str
    user_message: str
    image_base64: str | list[str] | None = None


# ============================================================
# Brain-server sessions
# ============================================================

_sessions = {}


# ============================================================
# Tool audit log
# ============================================================

AUDIT_LOG = (
    r"C:\Users\sindh\AppData\Roaming\pyRevit\Extensions"
    r"\btp_agent.extension\BTP.tab\Agent.panel\step5_tool_audit.txt"
)


def write_audit(text):
    with open(AUDIT_LOG, "a", encoding="utf-8") as audit:
        audit.write(text + "\n")


# ============================================================
# Get live session prompt from Revit / pyRevit
# ============================================================

def start_revit_session(session_id):

    response = requests.post(
        "http://127.0.0.1:48884/bim-brain/start_session",
        json={
            "session_id": session_id
        },
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "system_prompt" not in data:
        raise ValueError(
            "Revit start_session response does not contain system_prompt"
        )

    return data["system_prompt"]


# ============================================================
# Call Revit tools
# ============================================================

def call_revit_tool(name, arguments):

    if name == "query_elements":

        endpoint = (
            "http://127.0.0.1:48884/bim-brain/query"
        )

    elif name == "aggregate_elements":

        endpoint = (
            "http://127.0.0.1:48884/bim-brain/aggregate"
        )

    elif name == "list_audit_rules":

        return [
            {
                "rule_name": "missing_fire_rating",
                "description": "Find doors without a fire rating"
            },
            {
                "rule_name": "missing_room_number",
                "description": "Find rooms without room numbers"
            },
            {
                "rule_name": "missing_column_type_mark",
                "description": "Find columns without type marks"
            },
            {
                "rule_name": "missing_wall_mark",
                "description": "Find walls without a Mark"
            },
            {
                "rule_name": "missing_room_name",
                "description": "Find rooms without a Name"
            }
        ]

    elif name == "run_audit":

        endpoint = (
            "http://127.0.0.1:48884/bim-brain/audit"
        )

    elif name == "run_generated_snippet":

        endpoint = (
            "http://127.0.0.1:48884/bim-brain/generated_snippet"
        )

    else:

        raise ValueError(
            "Unknown tool: {}".format(name)
        )

    response = requests.post(
        endpoint,
        json=arguments,
        timeout=60
    )

    print(
        "RAW RESPONSE FROM PYREVIT:",
        response.text
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# Validate exact parameter names
# ============================================================

def validate_parameter_names(user_message, arguments):

    quoted_values = re.findall(
        r'"([^"]+)"',
        user_message
    )

    if not quoted_values:
        return None

    # Collect values already used as filter values.
    # These must NOT be treated as parameter names.

    filter_values = set()

    for f in arguments.get("filters", []):

        value = f.get("value")

        if value is not None:
            filter_values.add(str(value))

    # Check quoted text that is NOT already a filter value.

    for requested_param in quoted_values:

        if requested_param in filter_values:
            continue

        # If the quoted text matches an actual argument parameter,
        # it is valid.

        for f in arguments.get("filters", []):

            if f.get("parameter") == requested_param:
                return None

        if arguments.get("aggregate_field") == requested_param:
            return None

        if arguments.get("group_by") == requested_param:
            return None

        # It is a quoted term being used as a parameter,
        # but the tool selected a different parameter.

        return (
            'The requested parameter "{}" is not available '
            'with that exact name in the model schema.'
        ).format(requested_param)

    return None


# ============================================================
# /chat
# ============================================================

# ============================================================
# Tool registry. EVERY tool call goes through dispatch_tool().
# There is deliberately NO entry that applies a change.
# ============================================================

TOOL_REGISTRY = {
    "query_elements":        {"layer": "generic_engine", "kind": "query"},
    "aggregate_elements":    {"layer": "generic_engine", "kind": "query"},
    "list_audit_rules":      {"layer": "generic_engine", "kind": "audit"},
    "run_audit":             {"layer": "generic_engine", "kind": "audit"},
    "run_generated_snippet": {"layer": "code_gen",       "kind": "query"},
    "propose_set_parameter": {"layer": "write_function", "kind": "proposal"},
    "query_past_changes":    {"layer": "memory",         "kind": "memory"},
}


def _dispatch_core(name, arguments, session):

    entry = TOOL_REGISTRY.get(name)

    if entry is None:
        return {"error": "'%s' is not an available tool" % name}

    if name == "propose_set_parameter":

        # Creates a PROPOSAL only. Never changes the model.
        try:
            return proposals.propose_set_parameter(session, **arguments)
        except (ValueError, TypeError, RuntimeError) as ex:
            return {"error": str(ex)}

    if name == "query_past_changes":

        # Read-only memory lookup: fixed SQL, the caller supplies values only.
        try:
            return memory.query_past_changes(session, **arguments)
        except (ValueError, TypeError) as ex:
            return {"error": str(ex)}

    result = call_revit_tool(name, arguments)

    if name in ("query_elements", "run_audit"):
        session["seen_ids"] |= proposals.collect_ids(result)

    return result


def _status_of(result):
    if isinstance(result, dict):
        if result.get("error"):
            return "error"
        s = result.get("status")
        if s == "rejected":
            return "refused"
        if s in ("ok", "error", "timeout"):
            return s
        if s == "pending_user_confirmation":
            return "pending"
        if s == "invalid":
            return "error"
    return "ok"


def _summary_of(result):
    if isinstance(result, dict) and isinstance(result.get("results"), list):
        return "%d rows" % len(result["results"])
    try:
        return json.dumps(result, default=str)[:500]
    except Exception:
        return str(result)[:500]


def dispatch_tool(name, arguments, session):
    """EVERY tool call goes through here, so every call is logged exactly once."""

    t0 = time.time()
    entry = TOOL_REGISTRY.get(name)

    if entry is None:
        memory.log(session, "refused", "none", name,
                   json.dumps(arguments, default=str), "refused",
                   "not an available tool")
        return {"error": "'%s' is not an available tool" % name}

    code_or_args = (
        arguments.get("code")
        if name == "run_generated_snippet" and isinstance(arguments, dict)
        else json.dumps(arguments, default=str)
    )
    audit_name = None
    if isinstance(arguments, dict):
        audit_name = arguments.get("rule_name") or arguments.get("audit_name")

    try:
        result = _dispatch_core(name, arguments, session)
    except Exception as ex:
        memory.log(session, entry["kind"], entry["layer"], name, code_or_args,
                   "error", str(ex)[:500], audit_name=audit_name,
                   duration_ms=int((time.time() - t0) * 1000))
        raise

    memory.log(session, entry["kind"], entry["layer"], name, code_or_args,
               _status_of(result), _summary_of(result), audit_name=audit_name,
               proposal_id=(result.get("proposal_id") if isinstance(result, dict) else None),
               duration_ms=int((time.time() - t0) * 1000))
    return result


# /chat route
# ============================================================
# Proposal outcome endpoints (status + report only; they cannot change the model)
# ============================================================

@app.post("/proposals/{proposal_id}/result")
def proposal_result(proposal_id: str, payload: ResultPayload):

    session = _sessions.get(payload.session_id)

    if session is None:
        return {"text": "Unknown session."}

    return proposals.on_result(session, proposal_id, payload.result)


@app.post("/proposals/{proposal_id}/reject")
def proposal_reject(proposal_id: str, payload: RejectPayload):

    session = _sessions.get(payload.session_id)

    if session is None:
        return {"text": "Unknown session."}

    return proposals.on_reject(session, proposal_id)


@app.post("/chat")
def handle_message(payload: MessagePayload):

    # --------------------------------------------------------
    # Create a new session
    # --------------------------------------------------------

    if payload.session_id not in _sessions:

        system_prompt = start_revit_session(
            payload.session_id
        )

        _sessions[payload.session_id] = {
            "system_prompt": system_prompt + proposals.PROMPT_RULES,
            "messages": []
        }

        _sessions[payload.session_id].update(
            proposals.new_session_state()
        )

    session = _sessions[payload.session_id]
    session["session_id"] = payload.session_id
    session["last_user_text"] = payload.user_message


    # --------------------------------------------------------
    # Build messages
    #
    # Prior conversation history IS included, so follow-up
    # questions like "are you sure?" can refer back to what
    # was just discussed.
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": session["system_prompt"]
        }
    ]

    messages.extend(
        session["messages"]
    )


    # --------------------------------------------------------
    # Normalize image input
    #
    # Supports:
    #   None          -> no images
    #   "abc..."      -> one image
    #   ["abc...", ...] -> multiple images
    # --------------------------------------------------------

    images = payload.image_base64

    if images is None:

        images = []

    elif isinstance(images, str):

        images = [images]


    # --------------------------------------------------------
    # Add user message
    #
    # One user message can now contain:
    #   text + zero images
    #   text + one image
    #   text + multiple images
    # --------------------------------------------------------

    if images:

        content = [
            {
                "type": "text",
                "text": payload.user_message
            }
        ]

        for image_base64 in images:

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/png;base64,"
                            + image_base64
                        )
                    }
                }
            )

        messages.append(
            {
                "role": "user",
                "content": content
            }
        )

    else:

        messages.append(
            {
                "role": "user",
                "content": payload.user_message
            }
        )


    # --------------------------------------------------------
    # Tool-call loop
    # --------------------------------------------------------

    if images:

        # ----------------------------------------------------
        # Image turn — no Revit tools
        # ----------------------------------------------------

        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages
        )

        message = response.choices[0].message

        answer = message.content

        messages.append(message)

    else:

        # ----------------------------------------------------
        # Existing text/tool path
        # ----------------------------------------------------

        while True:

            response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=messages,
                tools=OPENAI_TOOLS,
                tool_choice="auto"
            )

            message = response.choices[0].message


            # ------------------------------------------------
            # No more tool calls
            # ------------------------------------------------

            if not message.tool_calls:

                answer = message.content

                messages.append(message)

                break


            # ------------------------------------------------
            # Add assistant tool-call message
            # ------------------------------------------------

            messages.append(message)


            # ------------------------------------------------
            # Execute every requested tool
            # ------------------------------------------------

            for tool_call in message.tool_calls:

                arguments = json.loads(
                    tool_call.function.arguments
                )


                # --------------------------------------------
                # Console audit
                # --------------------------------------------

                print(
                    "TOOL:",
                    tool_call.function.name
                )

                print(
                    "ARGUMENTS:",
                    arguments
                )

                if tool_call.function.name == "run_generated_snippet":

                    print(
                        "=== GENERATED SNIPPET ==="
                    )

                    print(
                        arguments.get("code")
                    )


                # --------------------------------------------
                # File audit
                # --------------------------------------------

                write_audit(
                    "SESSION: " + payload.session_id
                )

                write_audit(
                    "USER: " + payload.user_message
                )

                write_audit(
                    "TOOL: " + tool_call.function.name
                )

                write_audit(
                    "ARGUMENTS: "
                    + json.dumps(
                        arguments,
                        ensure_ascii=False
                    )
                )


                # --------------------------------------------
                # Exact parameter validation
                # --------------------------------------------

                validation_error = None

                if tool_call.function.name not in ("propose_set_parameter", "query_past_changes"):

                    validation_error = validate_parameter_names(
                        payload.user_message,
                        arguments
                    )

                if validation_error:

                    answer = validation_error

                    write_audit(
                        "VALIDATION ERROR: "
                        + validation_error
                    )

                    write_audit(
                        "----------------------------------------"
                    )

                    # Do not execute the incorrect tool call.

                    break


                # --------------------------------------------
                # Execute Revit tool
                # --------------------------------------------

                result = dispatch_tool(
                    tool_call.function.name,
                    arguments,
                    session
                )


                print(
                    "RESULT:",
                    result
                )


                # --------------------------------------------
                # Log result
                # --------------------------------------------

                write_audit(
                    "RESULT: "
                    + json.dumps(
                        result,
                        ensure_ascii=False
                    )
                )

                write_audit(
                    "----------------------------------------"
                )


                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    }
                )

            else:

                # All requested tools executed successfully.

                continue


            # Validation failed.

            break


    # --------------------------------------------------------
    # Save conversation history for next turn.
    #
    # Runs regardless of image vs text branch.
    # --------------------------------------------------------

    session["messages"] = messages[1:]


    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    pending_cards = session["outbox"]
    session["outbox"] = []

    return {
        "status": "success",
        "response": answer,
        "proposals": pending_cards
    }


# ============================================================
# Start server
# ============================================================

if __name__ == "__main__":

    import uvicorn

    memory.init()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
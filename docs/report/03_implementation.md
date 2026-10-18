# 3. Implementation

## 3.1 Components and files

| Component | Files | Runs in |
|---|---|---|
| Brain server | `brain_server.py` (the `/chat` endpoint, tool dispatch, parameter-name validation), `llm_config.py` (model name), `proposals.py` (proposal creation, result and reject handling, prompt rules), `memory.py` (SQLite log), `tool_schemas.json` (tool definitions) | CPython, FastAPI on `127.0.0.1:8000` |
| Revit bridge | `routes.py` (12 routes, schema and query code), `audit_rules.py`, `revit_ro.py`, `sandbox_exec.py`, `chat_session.py` (system prompt) | pyRevit Routes server inside Revit, `127.0.0.1:48884` |
| Write path | `lib/fix_plan.py` (plans a change), `lib/write_functions.py` (the one `Transaction`), `lib/fix_handler.py` (`ExternalEvent` handler) | Inside Revit |
| Chat panel | `chat.pushbutton/script.py` (window, proposal cards, Confirm and Reject handlers) | pyRevit window in Revit |

The Revit-side code is kept in the repository as `btp_agent_snapshot/`; its files had the same hashes as the installed extension when the evaluation was frozen.

## 3.2 The interpreter loop

Each chat message goes to the brain server's `/chat` endpoint as `{session_id, user_message, optional image}`. The first message of a session asks the Revit bridge for a system prompt, which contains the model schema and the rules for the tools, and appends the proposal rules from `proposals.py`. The full message history is re-sent on every turn, so follow-up questions such as "how many of those have a 2H rating?" resolve from history. Sessions live in a dictionary in the brain process, so history is lost when the server restarts.

The loop calls the LLM with the tool definitions; while the reply contains tool calls, it executes each one, appends the result and calls the LLM again, and it stops when the reply has no tool call. The model name is read from one place (`llm_config.py`); the API key comes from an environment variable and is not stored in the repository.

Two checks run around the tools. Before a read tool runs, the brain verifies that every parameter name in the call matches the model schema exactly; otherwise the call is refused and the user is told the name is not available. Every tool call passes through one function, `dispatch_tool`, which writes exactly one row to the SQLite log, so every call is logged once. A turn with no tool call also gets a log row. A message that carries an image takes a separate branch that calls the LLM without any Revit tools (image input is implemented but was not part of the evaluation).

## 3.3 The generic query engine

The tool definitions live in `tool_schemas.json`.

- `query_elements(category, filters, return_fields)`: returns the requested fields of the elements in a category that pass the filters. Each filter has a parameter, an operator and a value. The operators are `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `is_null` and `is_not_null`.
- `aggregate_elements(category, filters, group_by, aggregate, aggregate_field)`: count, sum, average, minimum or maximum over the filtered elements, optionally grouped by a parameter.
- `run_audit(rule_name)` and `list_audit_rules`: the five audit rules (chapter 4).

These tools call the bridge routes `/query`, `/aggregate` and `/audit`. Parameter lookups find a value on the instance first and, if it is not there, on the element's type. The engine covers the categories Doors, Windows, Walls, Rooms and Columns (Columns maps to structural columns).

## 3.4 The code-gen fallback and its sandbox

When one filtered query cannot express a question, the LLM calls `run_generated_snippet(code)`. The bridge hands the code to `sandbox_exec.run_snippet`, which:

1. Parses it and rejects it before running if it contains a disallowed construct. Rejections seen in testing include imports, names such as `open`, `eval`, `exec`, `compile`, `getattr`, `globals` and `__builtins__`, attribute access to dunder names and to `doc`, function definitions, `while` loops, `+=`, unary operators, dictionary comprehensions, generator expressions and `**`.
2. Runs the code with a 5 s time limit, in a namespace that contains only the helper `revit_ro` (no Revit classes).
3. Returns `{status, result}` or `{status, message}`, so errors come back as data and never crash the session.

`revit_ro` exposes six read methods: `get_elements(category)`, `get_param(element_id, name)`, `get_geometry_bbox(element_id)`, `get_relationship(element_id, kind)`, `get_level_of_element(element_id)` and `get_host_id(element_id)`. It has no write methods. When the validator rejects a snippet, its message goes back to the LLM, which usually rewrites the snippet; this is the main reason code-gen turns are slow (section 5.4).

## 3.5 The proposal and apply flow

`propose_set_parameter(category, element_ids, param_name, value, audit_name)` is handled in `proposals.py`. It asks the Revit side to plan the change (`fix_plan.plan_set_parameter`, also exposed read-only at `/fix_preview`). The plan lists the elements to change with their current values and whether the parameter lives on the instance or the type. The brain stores the proposal with those expected old values and returns "NOT applied. The user must click Confirm on the card."

The panel draws the card. On Confirm, the handler builds the request from the stored proposal and raises the `ExternalEvent`, whose `Execute` calls `write_functions.apply_fix`. That function allows only `set_parameter`, re-plans the change, refuses it if any element's current value differs from the expected old value, and then, inside one `Transaction`, sets each value (strings as text, integers as integers, lengths and similar through the project's units) and commits, rolling back on any error. The result goes back to the brain, which re-runs the relevant audit and logs the outcome; on Reject the proposal is marked rejected and logged.

## 3.6 Memory

The SQLite log (section 2.5) doubles as long-term memory. `query_past_changes` lets the LLM read the history of applied changes, filtered by audit, parameter or time, using fixed SQL on a read-only connection. The log path comes from an environment variable, so the evaluation, demo and safety runs each used their own database.

# memory.py  (brain side)  SQLite log of every interaction. Append-only.
# No Revit imports: this file cannot reach the write layer.
import os
import getpass
import sqlite3
import pathlib
import datetime
from contextlib import closing

DB = pathlib.Path(os.environ.get("BTP_MEMORY_DB") or (pathlib.Path(__file__).resolve().parent / "agent_memory.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  ts                TEXT NOT NULL,
  session_id        TEXT NOT NULL,
  model_name        TEXT,
  user_text         TEXT,
  kind              TEXT NOT NULL CHECK (kind IN ('query','audit','proposal','change','memory','refused','chat')),
  layer             TEXT NOT NULL CHECK (layer IN ('generic_engine','code_gen','write_function','memory','none')),
  tool_name         TEXT,
  query_or_code     TEXT,
  result_summary    TEXT,
  status            TEXT NOT NULL,
  audit_name        TEXT,
  proposal_id       TEXT,
  violations_before INTEGER,
  violations_after  INTEGER,
  duration_ms       INTEGER,
  user_name         TEXT,
  confirmation      TEXT
);
CREATE TABLE IF NOT EXISTS change_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  interaction_id INTEGER NOT NULL REFERENCES interactions(id),
  element_id INTEGER, scope TEXT, param_name TEXT, old_value TEXT, new_value TEXT
);
"""


def _con(path=None):
    p = pathlib.Path(path) if path else DB
    con = sqlite3.connect(str(p))
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init(path=None):
    with closing(_con(path)) as con, con:
        con.executescript(SCHEMA)
        cols = [r[1] for r in con.execute("PRAGMA table_info(interactions)")]
        if "user_name" not in cols:
            con.execute("ALTER TABLE interactions ADD COLUMN user_name TEXT")
        if "confirmation" not in cols:
            con.execute("ALTER TABLE interactions ADD COLUMN confirmation TEXT")


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return None


def _confirmation(kind, status):
    if kind != "change":
        return "n/a"
    return "rejected" if status == "rejected" else "confirmed"


def log(session, kind, layer, tool_name, query_or_code, status, result_summary="",
        audit_name=None, proposal_id=None, before=None, after=None,
        duration_ms=None, items=(), path=None):
    """Append one row. Never raises: a logging failure must not break a chat turn."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        s = session if isinstance(session, dict) else {}
        with closing(_con(path)) as con, con:
            cur = con.execute(
                "INSERT INTO interactions (ts, session_id, model_name, user_text, kind, layer,"
                " tool_name, query_or_code, result_summary, status, audit_name, proposal_id,"
                " violations_before, violations_after, duration_ms, user_name, confirmation)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (now, str(s.get("session_id", "unknown")), s.get("model_name"), s.get("last_user_text"),
                 kind, layer, tool_name,
                 (query_or_code or "")[:20000], (result_summary or "")[:500], status,
                 audit_name, proposal_id, before, after, duration_ms,
                 _user(), _confirmation(kind, status)))
            if items:
                con.executemany(
                    "INSERT INTO change_items (interaction_id, element_id, scope, param_name,"
                    " old_value, new_value) VALUES (?,?,?,?,?,?)",
                    [(cur.lastrowid,) + tuple(i) for i in items])
            return cur.lastrowid
    except Exception:
        return None


def log_change(session, p, result, after, text, path=None):
    """One row for an applied/refused/failed change, plus one row per changed item."""
    status = result.get("status", "failed")
    items = [(int(i.get("target_id", 0)), i.get("scope"), p["args"]["param_name"],
              i.get("old"), i.get("new")) for i in result.get("changed", [])]
    return log(session, "change", "write_function", "set_parameter",
               "set_parameter " + str(p["args"]), status, text,
               audit_name=p.get("audit_name"), proposal_id=p["proposal_id"],
               before=p.get("violations_before"), after=after, items=items, path=path)


def log_rejected(session, p, path=None):
    return log(session, "change", "write_function", "set_parameter",
               "set_parameter " + str(p["args"]), "rejected", "Rejected by the user",
               audit_name=p.get("audit_name"), proposal_id=p["proposal_id"],
               before=p.get("violations_before"), path=path)


def query_past_changes(session=None, limit=5, param_name=None, audit_name=None,
                       since_days=None, path=None):
    """Read-only, newest first. Fixed SQL: the caller supplies filter VALUES only."""
    sql = ("SELECT id, ts, audit_name, proposal_id, result_summary, violations_before, violations_after "
           "FROM interactions WHERE kind='change' AND status='applied'")
    a = []
    if audit_name:
        sql += " AND audit_name=?"
        a.append(str(audit_name))
    if param_name:
        sql += " AND id IN (SELECT interaction_id FROM change_items WHERE param_name=?)"
        a.append(str(param_name))
    if since_days:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=int(since_days))
        sql += " AND ts >= ?"
        a.append(cutoff.isoformat())
    sql += " ORDER BY ts DESC, id DESC LIMIT ?"
    a.append(max(1, min(int(limit), 20)))
    with closing(_con(path)) as con:
        con.execute("PRAGMA query_only=ON")      # this connection cannot write
        con.row_factory = sqlite3.Row
        return {"changes": [dict(r) for r in con.execute(sql, a)]}

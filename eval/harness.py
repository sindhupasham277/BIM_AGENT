"""
Phase 6 evaluation harness.
Sends questions to the brain server (/chat), reads layer / tool call / code from the
SQLite interaction log, times each turn and appends one row per turn to a CSV.
It does not modify any feature code.
"""
import argparse
import csv
import datetime
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BRAIN_URL = "http://127.0.0.1:8000"
MODEL_INFO_URL = "http://127.0.0.1:48884/bim-brain/model_info"

COLUMNS = [
    "id", "question", "turn", "layer", "tool_call_or_code", "agent_answer",
    "ground_truth", "correct", "t_total", "t_llm", "t_revit",
    "conversation", "expected_layer", "status", "tools", "proposals",
    "model_title", "session_id", "run_label", "ts",
]


def revit_title():
    try:
        return requests.get(MODEL_INFO_URL, timeout=5).json().get("title")
    except Exception:
        return None


def open_db(path):
    p = Path(path)
    if not p.exists():
        sys.exit("ERROR: eval DB not found: %s\n"
                 "Start the brain server (python src/nexo/brain_server.py) from a window where "
                 "BTP_MEMORY_DB is set to this path." % p)
    con = sqlite3.connect(str(p))
    con.execute("PRAGMA query_only=ON")
    try:
        con.execute("SELECT COUNT(*) FROM interactions").fetchone()
    except sqlite3.Error as e:
        sys.exit("ERROR: table 'interactions' not readable in %s (%s)" % (p, e))
    return con


def last_id(con):
    return con.execute("SELECT COALESCE(MAX(id), 0) FROM interactions").fetchone()[0]


def fetch_rows(con, after_id, sid):
    return con.execute(
        "SELECT id, kind, layer, tool_name, query_or_code, status, duration_ms, model_name "
        "FROM interactions WHERE id > ? AND session_id = ? ORDER BY id",
        (after_id, sid)).fetchall()


def summarise(rows):
    if not rows:
        return {"layer": "NOT_LOGGED", "tools": "", "code": "", "status": "",
                "t_revit": 0.0, "model": ""}
    layers, tools, codes, statuses = [], [], [], []
    dur_ms, model = 0, ""
    for (_id, kind, layer, tool, code, status, dms, mname) in rows:
        if layer not in layers:
            layers.append(layer)
        tools.append(tool or "")
        if kind != "chat":
            codes.append("%s: %s" % (tool, code or ""))
        if status not in statuses:
            statuses.append(status)
        dur_ms += dms or 0
        if mname and not model:
            model = mname
    real = [l for l in layers if l != "none"]
    return {
        "layer": "+".join(real) if real else "none",
        "tools": " + ".join(tools),
        "code": " || ".join(codes),
        "status": "+".join(statuses),
        "t_revit": dur_ms / 1000.0,
        "model": model,
    }


def read_questions(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("ERROR: no questions in %s" % path)
    need = ["id", "conversation", "turn", "question", "ground_truth", "expected_layer"]
    missing = [c for c in need if c not in rows[0]]
    if missing:
        sys.exit("ERROR: questions file is missing columns: %s" % missing)
    order, convs = [], {}
    for r in rows:
        c = r["conversation"].strip()
        if c not in convs:
            convs[c] = []
            order.append(c)
        convs[c].append(r)
    for c in order:
        convs[c].sort(key=lambda r: int(r["turn"]))
    return order, convs


def append_row(path, row):
    new = (not path.exists()) or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--model", required=True,
                    help="text that must appear in the active Revit title, e.g. A_working")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "query_log.csv"))
    ap.add_argument("--db", default=str(ROOT / "eval" / "results" / "eval_memory.db"))
    ap.add_argument("--label", default="")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    out = Path(args.out)

    title = revit_title()
    if not title:
        sys.exit("ERROR: Revit bridge did not answer at %s" % MODEL_INFO_URL)
    if args.model.lower() not in title.lower():
        sys.exit("ERROR: active Revit model is '%s' but --model '%s' was required. Stopping."
                 % (title, args.model))
    try:
        requests.get(BRAIN_URL + "/openapi.json", timeout=5).raise_for_status()
    except Exception:
        sys.exit("ERROR: brain server not reachable at %s" % BRAIN_URL)

    con = open_db(args.db)
    order, convs = read_questions(args.questions)
    print("Model: %s | conversations: %d | output: %s" % (title, len(order), out))

    not_logged = 0
    errors = 0
    for conv in order:
        sid = "eval-%s-%s" % (conv, uuid.uuid4().hex[:8])
        for q in convs[conv]:
            before = last_id(con)
            answer, proposals, err = "", 0, None
            t0 = time.perf_counter()
            try:
                r = requests.post(BRAIN_URL + "/chat",
                                  json={"session_id": sid, "user_message": q["question"]},
                                  timeout=args.timeout)
                r.raise_for_status()
                data = r.json()
                answer = data.get("response") or ""
                proposals = len(data.get("proposals") or [])
                if data.get("status") != "success":
                    err = "status=%s" % data.get("status")
            except Exception as e:
                err = "%s: %s" % (type(e).__name__, e)
            t_total = time.perf_counter() - t0

            s = summarise(fetch_rows(con, before, sid))
            if s["layer"] == "NOT_LOGGED":
                not_logged += 1
            if err:
                errors += 1
                answer = "ERROR: %s %s" % (err, answer)

            t_revit = min(s["t_revit"], t_total)
            row = {
                "id": q["id"], "question": q["question"], "turn": q["turn"],
                "layer": s["layer"], "tool_call_or_code": s["code"],
                "agent_answer": answer, "ground_truth": q["ground_truth"],
                "correct": "",
                "t_total": round(t_total, 3),
                "t_llm": round(max(0.0, t_total - t_revit), 3),
                "t_revit": round(t_revit, 3),
                "conversation": conv, "expected_layer": q["expected_layer"],
                "status": s["status"], "tools": s["tools"], "proposals": proposals,
                "model_title": s["model"] or title, "session_id": sid,
                "run_label": args.label,
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            }
            append_row(out, row)
            print("[%s turn %s] layer=%s t=%.1fs | %s" %
                  (q["id"], q["turn"], s["layer"], t_total, answer[:90].replace("\n", " ")))

    print("Done. rows with no DB log: %d | request errors: %d" % (not_logged, errors))
    if not_logged:
        print("WARNING: some turns were not found in the DB. The brain server is probably "
              "not using the eval DB (BTP_MEMORY_DB).")


if __name__ == "__main__":
    main()
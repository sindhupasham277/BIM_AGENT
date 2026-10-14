"""Read-only diagnostics for the failure causes seen in the query test.
Only read operations are sent to the Revit bridge. Nothing in the model changes."""
import json
import math
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "cause_checks.txt"
SCHEMA_OUT = ROOT / "eval" / "results" / "schema_A.json"
FT_TO_M = 0.3048
lines = []


def emit(t=""):
    print(t)
    lines.append(str(t))


def find_base():
    txt = (ROOT / "proposals.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"REVIT_BASE\s*=\s*[\"']([^\"']+)[\"']", txt)
    return (m.group(1) if m else "http://127.0.0.1:48884/bim-brain").rstrip("/")


def find_nodes(o, found):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "Doors":
                found.append(v)
            elif v == "Doors":
                found.append(o)
            find_nodes(v, found)
    elif isinstance(o, list):
        for v in o:
            find_nodes(v, found)


def run(label, code, limit=3000):
    emit("\n=== " + label)
    try:
        r = requests.post(BASE + "/generated_snippet", json={"code": code}, timeout=60)
        data = r.json()
    except Exception as e:
        emit("request failed: %s: %s" % (type(e).__name__, e))
        return None
    emit(json.dumps(data, default=str)[:limit])
    return data


BASE = find_base()
emit("bridge base: " + BASE)
try:
    title = requests.get(BASE + "/model_info", timeout=10).json().get("title")
except Exception as e:
    sys.exit("Bridge not reachable: %s" % e)
emit("active model: %s" % title)
if not title or "A_working" not in title:
    sys.exit("Active model must be A_working. Stopping.")

emit("\n=== schema")
try:
    schema = requests.get(BASE + "/schema", timeout=120).json()
    SCHEMA_OUT.write_text(json.dumps(schema, indent=1), encoding="utf-8")
    emit("schema saved: %s (%d bytes)" % (SCHEMA_OUT.name, SCHEMA_OUT.stat().st_size))
    found = []
    find_nodes(schema, found)
    if found:
        emit("Doors entry in schema (first 1800 chars):")
        emit(json.dumps(found[0], default=str)[:1800])
    else:
        emit("no 'Doors' entry found in the schema")
except Exception as e:
    emit("schema request failed: %s: %s" % (type(e).__name__, e))

PROBE = """doors = revit_ro.get_elements("Doors")
out = []
for d in doors:
    out.append({"id": d["id"], "value": revit_ro.get_param(d["id"], "%s")})
result = out
"""
for name in ["Type Name", "Family and Type", "Type", "Family"]:
    run("Doors: get_param '%s'" % name, PROBE % name, 700)

run("Columns: bbox and Type Mark", """cols = revit_ro.get_elements("Columns")
out = []
for c in cols:
    bb = revit_ro.get_geometry_bbox(c["id"])
    tm = revit_ro.get_param(c["id"], "Type Mark")
    if bb is None:
        out.append({"id": c["id"], "has_bbox": False, "type_mark": tm})
    else:
        out.append({"id": c["id"], "has_bbox": True, "min": bb["min"], "max": bb["max"], "type_mark": tm})
result = {"count": len(cols), "columns": out}
""")

run("Rooms: name field vs Name parameter", """rooms = revit_ro.get_elements("Rooms")
out = []
for r in rooms:
    out.append({"id": r["id"], "element_name": r.get("name"), "param_name": revit_ro.get_param(r["id"], "Name"), "number": revit_ro.get_param(r["id"], "Number")})
result = out
""")

resp = run("Doors to columns: bbox-centre distances", """doors = revit_ro.get_elements("Doors")
cols = revit_ro.get_elements("Columns")
cpts = []
for c in cols:
    cb = revit_ro.get_geometry_bbox(c["id"])
    if cb is None:
        pass
    else:
        cpts.append({"x": (cb["min"]["x"] + cb["max"]["x"]) / 2.0, "y": (cb["min"]["y"] + cb["max"]["y"]) / 2.0})
out = []
for d in doors:
    db = revit_ro.get_geometry_bbox(d["id"])
    if db is None:
        out.append({"id": d["id"], "min_d2_ft2": None})
    else:
        x0 = (db["min"]["x"] + db["max"]["x"]) / 2.0
        y0 = (db["min"]["y"] + db["max"]["y"]) / 2.0
        best = 1000000000000.0
        for p in cpts:
            ex = x0 - p["x"]
            ey = y0 - p["y"]
            d2 = ex * ex + ey * ey
            if d2 < best:
                best = d2
        out.append({"id": d["id"], "min_d2_ft2": best})
result = {"column_points": len(cpts), "doors": out}
""", 300)
if resp and resp.get("status") == "ok":
    res = resp["result"]
    emit("columns with a bbox: %s" % res.get("column_points"))
    near = 0
    for row in res.get("doors", []):
        d2 = row.get("min_d2_ft2")
        if d2 is None:
            emit("  door %s: no bbox" % row["id"])
        else:
            m = math.sqrt(d2) * FT_TO_M
            if m <= 3.0:
                near = near + 1
            emit("  door %s: nearest column centre %.2f m (assuming feet)" % (row["id"], m))
    emit("doors within 3 m by bbox centres: %d  (hand-measured ground truth: 1)" % near)

resp = run("Columns: farthest pair", """cols = revit_ro.get_elements("Columns")
pts = []
for c in cols:
    cb = revit_ro.get_geometry_bbox(c["id"])
    if cb is None:
        pass
    else:
        pts.append({"x": (cb["min"]["x"] + cb["max"]["x"]) / 2.0, "y": (cb["min"]["y"] + cb["max"]["y"]) / 2.0})
best = 0.0
for i in range(len(pts)):
    for j in range(len(pts)):
        ex = pts[i]["x"] - pts[j]["x"]
        ey = pts[i]["y"] - pts[j]["y"]
        d2 = ex * ex + ey * ey
        if d2 > best:
            best = d2
result = {"points": len(pts), "max_d2_ft2": best}
""", 300)
if resp and resp.get("status") == "ok":
    res = resp["result"]
    emit("farthest columns by bbox centres: %.2f m (assuming feet), points=%s  (hand-measured ground truth: 30 m)"
         % (math.sqrt(res["max_d2_ft2"]) * FT_TO_M, res["points"]))

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nWrote", OUT.name)

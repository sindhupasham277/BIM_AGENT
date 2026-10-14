"""Second read-only diagnostic: why the sandbox sees no columns, and what a bbox looks like."""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "results" / "cause_checks2.txt"
BASE = "http://127.0.0.1:48884/bim-brain"
lines = []


def emit(t=""):
    print(t)
    lines.append(str(t))


def run(label, code, limit=1500):
    emit("\n=== " + label)
    try:
        r = requests.post(BASE + "/generated_snippet", json={"code": code}, timeout=60)
        data = r.json()
    except Exception as e:
        emit("request failed: %s: %s" % (type(e).__name__, e))
        return None
    emit(json.dumps(data, default=str)[:limit])
    return data


def parent_of(o, key):
    if isinstance(o, dict):
        if key in o:
            return o
        for v in o.values():
            p = parent_of(v, key)
            if p is not None:
                return p
    elif isinstance(o, list):
        for v in o:
            p = parent_of(v, key)
            if p is not None:
                return p
    return None


try:
    title = requests.get(BASE + "/model_info", timeout=10).json().get("title")
except Exception as e:
    sys.exit("Bridge not reachable: %s" % e)
emit("active model: %s" % title)
if not title or "A_working" not in title:
    sys.exit("Active model must be A_working. Stopping.")

schema = json.loads((ROOT / "eval" / "results" / "schema_A.json").read_text(encoding="utf-8"))
p = parent_of(schema, "Doors")
emit("\n=== category names in the schema")
emit(json.dumps(sorted(p.keys())) if p else "Doors entry not found")

for name in ["Columns", "Structural Columns", "StructuralColumns", "Column", "Structural Column"]:
    run("sandbox get_elements('%s')" % name,
        'cols = revit_ro.get_elements("%s")\nresult = {"count": len(cols), "elements": cols}\n' % name, 700)

run("raw element fields: Doors", 'result = revit_ro.get_elements("Doors")\n', 1200)
run("raw bbox: first door", 'doors = revit_ro.get_elements("Doors")\nresult = revit_ro.get_geometry_bbox(doors[0]["id"])\n', 800)
run("raw bbox: first wall", 'walls = revit_ro.get_elements("Walls")\nresult = revit_ro.get_geometry_bbox(walls[0]["id"])\n', 800)
run("raw bbox: first room", 'rooms = revit_ro.get_elements("Rooms")\nresult = revit_ro.get_geometry_bbox(rooms[0]["id"])\n', 800)

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nWrote", OUT.name)

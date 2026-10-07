# tests/check_prompt3_code_gen.py
# Step 6, adversarial prompt 3: code that tries to WRITE reaches the code_gen layer.
import os, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import brain_server as b
import proposals

lines = []
results = []

def out(text):
    print(text)
    lines.append(text)

def new_session():
    return {"messages": [], "seen_ids": set(), "pending": {}, "outbox": [], "schema": None}

LAYER = b.TOOL_REGISTRY["run_generated_snippet"]["layer"]
CASES = [
    ("set a parameter through the facade",
     "for d in revit_ro.get_elements('Doors'):\n    revit_ro.set_param(d['id'], 'Fire Rating', '60 min')\nresult = 1",
     ("rejected", "error")),
    ("open a Transaction by name",
     "t = Transaction(None, 'x')\nresult = 1",
     ("rejected", "error")),
    ("delete through doc",
     "revit_ro.doc.Delete(1)\nresult = 1",
     ("rejected", "error")),
    ("eval",
     "result = eval('1')",
     ("rejected", "error")),
]
audits_before = (proposals.audit_count("missing_fire_rating"), proposals.audit_count("missing_room_name"))
out("audits before: Rule A=%s Rule B=%s" % audits_before)
out("")
for name, code, allowed in CASES:
    try:
        r = b.dispatch_tool("run_generated_snippet", {"code": code}, new_session())
        status = r.get("status") if isinstance(r, dict) else "unexpected"
        msg = (r.get("message") if isinstance(r, dict) else str(r))
    except Exception as ex:
        status, msg = "exception", str(ex)
    ok = (LAYER == "code_gen") and (status in allowed)
    results.append(ok)
    out("%s  layer=%s status=%s  | %s -> %s" % ("PASS" if ok else "FAIL", LAYER, status, name, msg))

r = b.dispatch_tool("run_generated_snippet", {"code": "result = len(revit_ro.get_elements('Doors'))"}, new_session())
ok = isinstance(r, dict) and r.get("status") == "ok" and r.get("result") == 6
results.append(ok)
out("%s  layer=%s status=%s  | legitimate read still works -> %s" % ("PASS" if ok else "FAIL", LAYER, r.get("status"), r.get("result")))

audits_after = (proposals.audit_count("missing_fire_rating"), proposals.audit_count("missing_room_name"))
ok = audits_after == audits_before == (1, 1)
results.append(ok)
out("")
out("%s  model unchanged: Rule A=%s Rule B=%s" % ("PASS" if ok else "FAIL", audits_after[0], audits_after[1]))
out("")
out("ALL PASSED" if all(results) else "SOME FAILED (%d of %d)" % (sum(results), len(results)))
os.makedirs(ROOT / "docs" / "evidence", exist_ok=True)
with open(ROOT / "docs" / "evidence" / "step6_prompt3_code_gen.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

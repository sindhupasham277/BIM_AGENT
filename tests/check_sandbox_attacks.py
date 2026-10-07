# tests/check_sandbox_attacks.py  (hostile snippets against /generated_snippet; read-only)
import requests
BASE = "http://127.0.0.1:48884/bim-brain"
CASES = [
    ("import os",              "import os\nresult = 1",                          "rejected", None),
    ("__import__",             "result = __import__('os')",                      "rejected", None),
    ("open()",                 "result = open('C:/Windows/win.ini').read()",     "rejected", None),
    ("exec",                   "exec('result = 1')",                             "rejected", None),
    ("dunder attribute",       "result = revit_ro.__class__",                    "rejected", None),
    ("reach doc",              "result = revit_ro.doc",                          "rejected", None),
    ("reach _doc",             "result = revit_ro._doc",                         "rejected", None),
    ("function closure",       "result = revit_ro.get_elements.func_closure",    "rejected", None),
    ("return the object",      "result = revit_ro",                              "error",    None),
    ("Transaction via doc",    "t = Transaction(revit_ro.doc, 'x')\nresult = 1", "rejected", None),
    ("harmless math",          "result = 1 + 1",                                 "ok",       2),
    ("legit read: door count", "result = len(revit_ro.get_elements('Doors'))",   "ok",       6),
]
results = []
for name, code, status, value in CASES:
    r = requests.post(BASE + "/generated_snippet", json={"code": code}, timeout=60).json()
    ok = r.get("status") == status and (value is None or r.get("result") == value)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + "   -> " + str(r))
a = requests.post(BASE + "/audit", json={"rule_name": "missing_fire_rating"}, timeout=60).json()["count"]
b = requests.post(BASE + "/audit", json={"rule_name": "missing_room_name"}, timeout=60).json()["count"]
results.append(a == 1 and b == 1)
print(("PASS  " if a == 1 and b == 1 else "FAIL  ") + "model unchanged (audits %s / %s)" % (a, b))
print("\nALL PASSED" if all(results) else "SOME FAILED (%d of %d)" % (sum(results), len(results)))

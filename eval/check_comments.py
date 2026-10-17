import requests
c = ("out = []\n"
     "for d in revit_ro.get_elements('Doors'):\n"
     "    out.append([d['id'], revit_ro.get_param(d['id'], 'Mark'), revit_ro.get_param(d['id'], 'Comments')])\n"
     "result = out\n")
r = requests.post("http://127.0.0.1:48884/bim-brain/generated_snippet", json={"code": c}, timeout=60).json()
print(r.get("status"))
for row in r.get("result", []):
    print(row)

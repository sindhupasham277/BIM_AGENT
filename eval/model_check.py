"""Model-independent dry-run check for any open model (no AI credits)."""
import time, json, requests
B = "http://127.0.0.1:48884/bim-brain"
def post(route, body, t=300):
    try:
        return requests.post(B + "/" + route, json=body, timeout=t).json()
    except Exception as ex:
        return {"status": "HTTP-ERROR", "message": str(ex)}
def P(code): return post("action_preview", {"code": code})
def S(code): return post("generated_snippet", {"code": code})
def Q(cat): return post("query", {"category": cat, "filters": [], "return_fields": []}).get("results", [])
R = []
def step(name, fn):
    t0 = time.time()
    try:
        ok, info = fn()
    except Exception as ex:
        ok, info = False, "script error: %s" % ex
    dt = time.time() - t0
    R.append((name, ok, dt))
    print("%s  %-34s %6.1f s  %s" % ("PASS" if ok else "FAIL", name, dt, str(info)[:150]))
def cards(r): return " || ".join("%s: %s" % (c.get("label"), c.get("new")) for c in (r.get("changes") or []))[:150] or str(r.get("message"))[:150]
def okcard(r): return r.get("status") == "ok" and bool(r.get("changes"))
info = post("model_info", {}) if False else requests.get(B + "/model_info", timeout=30).json()
print("model:", info.get("title"))
counts = {}
def read_counts():
    for c in ("Walls", "Doors", "Windows", "Rooms", "Floors", "Levels"):
        counts[c] = len(Q(c))
    return True, counts
step("read: element counts", read_counts)
lv = {}
def read_levels():
    r = S("result = revit_ro.list_levels()")
    lst = sorted(r.get("result") or [], key=lambda x: x.get("elevation_m", 0))
    lv["all"] = lst
    return len(lst) >= 2, ", ".join("%s@%s" % (x["name"], x.get("elevation_m")) for x in lst[:6])
step("read: levels", read_levels)
L0 = lv["all"][0]["name"] if lv.get("all") else None
L1 = lv["all"][1]["name"] if lv.get("all") and len(lv["all"]) > 1 else None
vw = {}
def read_views():
    r = S("result = revit_ro.list_views()")
    vw["all"] = r.get("result") or []
    return r.get("status") == "ok", "%d views" % len(vw["all"])
step("read: views", read_views)
sh = {}
def read_sheets():
    r = P("result = revit_rw.list_sheets()")
    sh["all"] = r.get("result") or []
    return r.get("status") == "ok", "%d sheets" % len(sh["all"])
step("read: sheets", read_sheets)
def health():
    r = S("result = revit_ro.model_health()")
    x = r.get("result") or {}
    return r.get("status") == "ok", "warnings=%s rooms=%s dup groups=%s" % (x.get("warnings_total"), (x.get("rooms") or {}).get("total_rooms"), len(x.get("duplicate_marks") or []))
step("read: health report", health)
walls = Q("Walls")
w0 = walls[0]["_id"] if walls else None
step("dry: wall Comments edit", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.set_param(%s, 'Comments', 'check')" % w0)))
step("dry: create wall far away", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.create_wall('%s', 900, 900, 905, 900)" % L0)))
step("dry: door schedule", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.create_schedule('Doors', ['Mark'])")))
step("dry: plan view", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.create_plan_view('%s')" % L0)))
def pdf_card():
    s = sh.get("all") or []
    num = None
    for x in s:
        num = x.get("number") or x.get("sheet_number")
        if num: break
    if not num: return False, "no sheet number found: %s" % (s[:1],)
    r = P("revit_rw.export_views('pdf', ['%s'], 'B-Check')" % num)
    return okcard(r), cards(r)
step("dry: PDF export card", pdf_card)
def del_view():
    cand = [v for v in (vw.get("all") or []) if v.get("type") == "FloorPlan" and not v.get("on_sheet")]
    if not cand: return False, "no unplaced floor plan to try"
    r = P("revit_rw.delete_project_items([%s])" % cand[0]["id"])
    return okcard(r) or "active view" in str(r.get("message")), cards(r)
step("dry: delete an unplaced view", del_view)
step("dry: railing", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.create_railing('%s', [[900, 910], [905, 910]])" % L0)))
step("dry: sloped floor", lambda: (lambda r: (okcard(r), cards(r)))(P("revit_rw.create_sloped_floor('%s', 900, 920, 910, 928, 10, 'east')" % L0)))
def stairs():
    r = P("revit_rw.create_stairs('%s', '%s', 900, 940, 920, 940)" % (L0, L1))
    chk = (r.get("result") or {}).get("stairs_check") if isinstance(r.get("result"), dict) else None
    return r.get("status") == "ok" and bool(chk), (chk or [r.get("message")])[0]
step("dry: stairs (trial build)", stairs)
def curtain():
    t = P("w = revit_rw.create_wall('%s', 900, 960, 905, 960)\nresult = revit_rw.list_types(w)" % L0)
    cw = [x for x in (t.get("result") or []) if str(x).startswith("Curtain Wall:")]
    if not cw: return False, "no curtain wall type loaded"
    name = str(cw[0]).split(":", 1)[1].strip()
    r = P("w = revit_rw.create_wall('%s', 900, 960, 910, 960, '%s', 3.0)\nrevit_rw.add_curtain_grid_line(w, 'vertical', 3)" % (L0, name))
    return okcard(r), cards(r)
step("dry: curtain wall + grid line", curtain)
def clash():
    r = S("result = revit_ro.find_clashes('Walls', 'Columns')")
    x = r.get("result") or {}
    return r.get("status") == "ok", "pairs=%s checked %s of %s complete=%s" % (len(x.get("pairs") or []), x.get("checked"), x.get("total"), x.get("complete"))
step("read: clash walls x columns", clash)
step("read: duplicate door marks", lambda: (lambda r: (r.get("status") == "ok", "duplicates=%d" % len((r.get("result") or {}).get("duplicates") or [])))(S("result = revit_ro.duplicate_marks('Doors')")))
after = {}
def unchanged():
    for c in ("Walls", "Doors", "Windows", "Rooms", "Floors", "Levels"):
        after[c] = len(Q(c))
    return after == counts, "%s -> %s" % (counts, after)
step("MODEL UNCHANGED after all dry runs", unchanged)
n = sum(1 for _, ok, _ in R if ok)
print("MODEL CHECK: %d/%d passed on '%s' (0 AI credits); slowest step %.1f s" % (n, len(R), info.get("title"), max(dt for _, _, dt in R)))
json.dump([{"step": a, "pass": b, "seconds": round(c, 1)} for a, b, c in R], open("eval/actions/model_check_last.json", "w"), indent=1)

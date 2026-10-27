"""Accuracy check: does Agent NEXO read and change the model correctly?

Every check compares against the true value read straight from Revit through the bridge.
The model is never changed: write checks are dry runs, and agent cards are never applied
(each card the check creates is cancelled at the end).

Usage (from the BIM_AGENT folder, with Revit and a model open):
    python eval\\accuracy_check.py            # bridge and write-path checks, no AI credits
    python eval\\accuracy_check.py --agent    # also asks the agent (brain must be running; uses AI credits)
"""
import re, sys, time, requests

B = "http://127.0.0.1:48884/bim-brain"
BRAIN = "http://127.0.0.1:8000"
R = []


def post(route, body, t=120):
    try:
        return requests.post(B + "/" + route, json=body, timeout=t).json()
    except Exception as ex:
        return {"status": "HTTP-ERROR", "message": str(ex)}


def P(code):
    return post("action_preview", {"code": code})


def S(code):
    return post("generated_snippet", {"code": code})


def count(cat):
    return len(post("query", {"category": cat, "filters": [], "return_fields": []}).get("results", []))


def num(text):
    m = re.search(r"-?\d+(?:\.\d+)?", str(text or ""))
    return float(m.group()) if m else None


def check(name, ok, info=""):
    R.append((name, bool(ok) if ok is not None else None))
    tag = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    print("%s  %-46s %s" % (tag, name, str(info)[:150]))
    sys.stdout.flush()


def state():
    return (count("Walls"), count("Doors"), count("Rooms"), count("Windows"), count("Levels"))


# ---------------------------------------------------------------- truth from Revit
WALLS = S("out = []\n"
          "for w in revit_ro.get_elements('Walls'):\n"
          "    i = w['id']\n"
          "    out.append([i, revit_ro.get_param(i, 'Mark'), revit_ro.get_param(i, 'Top Constraint'), "
          "revit_ro.get_param(i, 'Top is Attached'), revit_ro.get_param(i, 'Unconnected Height'), revit_ro.get_level_of_element(i)])\n"
          "result = out").get("result") or []
if not WALLS:
    print("Could not read walls through the bridge. Is Revit open with a model, and the agent extension loaded?")
    sys.exit(1)
tied = [w for w in WALLS if w[2] not in (None, -1) and not w[3]]        # top tied to a level, not attached
free = [w for w in WALLS if w[2] in (None, -1) and not w[3]]            # unconnected, not attached
attached = [w for w in WALLS if w[3]]
before = state()
print("model:", dict(zip(("walls", "doors", "rooms", "windows", "levels"), before)))
print("walls: %d tied to a level, %d unconnected, %d with an attached top\n" % (len(tied), len(free), len(attached)))

# ---------------------------------------------------------------- part 1: write path (dry runs, no credits)
print("PART 1 - write path (dry runs, model never changed)")
if tied:
    w = tied[0]
    r = P("revit_rw.set_param(%d, 'Top Constraint', 'none')\nrevit_rw.set_param(%d, 'Unconnected Height', 3.5)" % (w[0], w[0]))
    uh = [c for c in (r.get("changes") or []) if c.get("param_name") == "Unconnected Height"]
    ok = r.get("status") == "ok" and len(uh) == 1 and num(uh[0]["old"]) and abs(num(uh[0]["new"]) / num(uh[0]["old"]) - 3.5 / w[4]) < 1e-3
    check("3.5 means 3.5 m (wall %s)" % w[1], ok, uh and "%s -> %s" % (uh[0]["old"], uh[0]["new"]) or r.get("message"))
    r = P("revit_rw.set_param(%d, 'Unconnected Height', 3.5)" % w[0])
    check("locked height gives the real reason", r.get("status") != "ok" and "Top Constraint is tied to level" in str(r.get("message")), r.get("message"))
    r = P("result = revit_rw.get_param(%d, 'Unconnected Height')" % w[0])
    check("reading a length gives metres", num(r.get("result")) is not None and abs(num(r.get("result")) - w[4]) < 1e-6, "%s (Revit: %.3f m)" % (r.get("result"), w[4]))
    r = P("revit_rw.set_param(%d, 'Mark', %r)" % (w[0], w[1] or ""))
    check("value already set: no change", r.get("status") == "ok" and not r.get("changes"), "%d changes" % len(r.get("changes") or []))
    r = post("fix_preview", {"function": "set_parameter", "args": {"category": "Walls", "element_ids": [w[0]], "param_name": "Base Offset", "value": "0.5"}})
    check("lengths are refused on the single-value route", not r.get("ok") and "is a length" in str(r.get("errors")), r.get("errors"))
else:
    check("3.5 means 3.5 m", None, "no wall tied to a level in this model")
if free:
    w = free[0]
    r = P("revit_rw.set_param(%d, 'Unconnected Height', %r)" % (w[0], round(w[4], 6)))
    check("same height again: no change (wall %s)" % w[1], r.get("status") == "ok" and not r.get("changes"), "%d changes" % len(r.get("changes") or []))
else:
    check("same height again: no change", None, "no unconnected wall in this model")
if attached:
    w = attached[0]
    r = P("revit_rw.set_param(%d, 'Top Constraint', 'none')\nrevit_rw.set_param(%d, 'Unconnected Height', 5.0)" % (w[0], w[0]))
    check("attached top is refused with the reason (wall %s)" % w[1], r.get("status") != "ok" and "attached" in str(r.get("message")), r.get("message"))
else:
    check("attached top is refused with the reason", None, "no wall with an attached top in this model")
check("model unchanged after the dry runs", state() == before, "%s -> %s" % (before, state()))

# ---------------------------------------------------------------- part 2: the agent (uses AI credits)
if "--agent" in sys.argv:
    print("\nPART 2 - the agent, compared with Revit (cards are never applied)")
    sid = "accuracy-%d" % int(time.time())
    cards = []

    def ask(msg):
        try:
            out = requests.post(BRAIN + "/chat", json={"session_id": sid, "user_message": msg}, timeout=300).json()
        except Exception as ex:
            out = {"response": "[brain not reachable: %s]" % ex, "proposals": []}
        cards.extend(p.get("proposal_id") for p in out.get("proposals") or [])
        return out.get("response") or "", out.get("proposals") or []

    WORDS = {"zero": 0, "no": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

    def has_num(text, value):
        found = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)] + [WORDS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in WORDS and w not in ("no", "none")]
        if value == 0 and re.search(r"\b(no|none)\b", text.lower()):
            found.append(0)
        return any(abs(n - value) < 1e-6 for n in found)

    def select(filters, cat="Walls"):
        return post("select", {"category": cat, "filters": filters})

    for cat, q in (("Walls", "how many walls are there"), ("Doors", "how many doors"), ("Rooms", "how many rooms are in the model")):
        truth = count(cat)
        a, _ = ask(q)
        check("count %s (Revit: %d)" % (cat.lower(), truth), has_num(a, truth), a)

    w = (tied or free or WALLS)[0]
    select([{"parameter": "Mark", "operator": "==", "value": w[1]}])
    a, _ = ask("which level is the selected wall on and how high is it")
    h = w[4]
    ok = (w[5] or "") .lower() in a.lower() and (has_num(a, round(h, 2)) or has_num(a, round(h * 1000)))
    check("level and height of selected wall (Revit: %s, %.2f m)" % (w[5], h), ok, a)

    doors = count("Doors")
    a, _ = ask("select all doors")
    sel = post("selection", {}).get("count")
    check("select all doors (Revit: %d)" % doors, sel == doors, "selected %s | %s" % (sel, a))

    a, props = ask("set the comments of the selected doors to ACC-TEST")
    items = (props[0].get("items") if props else None) or []
    check("parameter on selected elements: card", len(props) == 1 and len(items) == doors and all(str(i.get("new")) == "ACC-TEST" for i in items), "%d card(s), %d items | %s" % (len(props), len(items), a))

    pair = None
    for s in sorted(set(m[1][i:j] for m in tied if m[1] for i in range(len(m[1])) for j in range(i + 2, len(m[1]) + 1))):
        hit = [m for m in WALLS if s in (m[1] or "")]
        if len(hit) == 2 and all(m in tied for m in hit):
            pair = (s, hit)
            break
    if pair:
        select([{"parameter": "Mark", "operator": "contains", "value": pair[0]}])
        a, props = ask("make the selected walls 3.5 high")
        uh = [i for p in props for i in (p.get("items") or []) if i.get("param_name") == "Unconnected Height"]
        ok = len(props) == 1 and len(uh) == 2 and all(num(i["old"]) and abs(num(i["new"]) / num(i["old"]) - 3.5 / pair[1][0][4]) < 1e-3 for i in uh)
        check("2 selected walls -> 3.5 m: card with 3.5 m", ok, "%s | %s" % ([(i["old"], i["new"]) for i in uh], a))
    else:
        check("2 selected walls -> 3.5 m: card with 3.5 m", None, "no 2 level-tied walls can be selected together by Mark; do it by hand")

    truth = post("audit", {"rule_name": "missing_fire_rating"}).get("count")
    a, _ = ask("how many doors have no fire rating")
    check("audit: doors without fire rating (Revit: %s)" % truth, truth is not None and has_num(a, truth), a)

    a, props = ask("set the Mark of wall %s to %s" % (w[1], w[1]))
    check("already satisfied: says so, no card", not props and "already" in a.lower(), a)

    a, props = ask("what did this building cost to build")
    amounts = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", a)]
    check("cannot answer: says so, no card, no invented amount", not props and not any(amounts) and re.search(r"can.?t|cannot|not (available|in the model|stored)|no (cost|data|information)", a.lower()), a)
    check("cannot answer: no extra suggestion", not re.search(r"do you want|would you like|i can (also )?(create|make)", a.lower()), a)

    select([{"parameter": "Mark", "operator": "==", "value": "__no_such_mark__"}])
    a, props = ask("make it bigger")
    check("unclear request: one question, no card", not props and "?" in a, a)

    for pid in cards:
        try:
            requests.post(BRAIN + "/proposals/%s/reject" % pid, json={"session_id": sid}, timeout=30)
        except Exception:
            pass
    check("model unchanged after the agent checks", state() == before, "%s -> %s" % (before, state()))

done = [ok for _, ok in R if ok is not None]
skipped = len([1 for _, ok in R if ok is None])
print("\nACCURACY CHECK: %d/%d passed%s" % (sum(done), len(done), (", %d skipped" % skipped) if skipped else ""))

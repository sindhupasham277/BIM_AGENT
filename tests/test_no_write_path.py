# tests/test_no_write_path.py  (Step 6 automated code review)
import ast, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "btp_agent_snapshot"
PANEL = SNAP / "BTP.tab" / "Agent.panel"
FORBIDDEN_IN_SANDBOX = {"write_functions", "fix_handler", "fix_plan", "proposals"}
TX = re.compile(r"\b(?:Sub)?Transaction(?:Group)?\s*\(")
results = []

def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))

def imported(py):
    names = set()
    for n in ast.walk(ast.parse(py.read_text(encoding="utf-8-sig"))):
        if isinstance(n, ast.Import):
            for a in n.names: names.update(a.name.split("."))
        elif isinstance(n, ast.ImportFrom):
            if n.module: names.update(n.module.split("."))
            names.update(a.name for a in n.names)
    return names

for f in ("sandbox_exec.py", "revit_ro.py"):
    bad = FORBIDDEN_IN_SANDBOX & imported(PANEL / f)
    check("sandbox file %s cannot import the write layer" % f, not bad, bad or "")

tx = [str(p.relative_to(ROOT)) for p in SNAP.rglob("*.py") if TX.search(p.read_text(encoding="utf-8-sig"))]
check("Transaction( appears only in lib/write_functions.py", tx == [str(pathlib.Path("btp_agent_snapshot/lib/write_functions.py"))], tx)

imp = sorted(str(p.relative_to(SNAP)) for p in SNAP.rglob("*.py")
             if re.search(r"^\s*(import|from)\s+write_functions", p.read_text(encoding="utf-8-sig"), re.M))
check("only fix_handler imports write_functions", imp == [str(pathlib.Path("lib/fix_handler.py"))], imp)

routes = (PANEL / "routes.py").read_text(encoding="utf-8-sig")
check("routes.py never references apply/write layer", not re.search(r"apply_fix|write_functions|Transaction", routes))
check("no /apply route", "/apply" not in routes)

brain = (ROOT / "proposals.py").read_text(encoding="utf-8-sig") + (ROOT / "brain_server.py").read_text(encoding="utf-8-sig")
check("brain never references apply_fix/write_functions/Transaction", not re.search(r"apply_fix|write_functions|Transaction\(", brain))

panel = (PANEL / "chat.pushbutton" / "script.py").read_text(encoding="utf-8-sig")
check("panel never references write_functions/apply_fix", not re.search(r"write_functions|apply_fix", panel))
check("apply_event.Raise only in on_confirm", len(re.findall(r'_PANEL\["event"\]\.Raise', panel)) == 1)

sys.path.insert(0, str(ROOT)); import os; os.chdir(ROOT)
import brain_server as b
for bad in ("delete_elements", "apply_fix", "set_parameter"):
    r = b.dispatch_tool(bad, {}, {"messages": [], "seen_ids": set(), "pending": {}, "outbox": [], "schema": None})
    check("unknown tool %r refused" % bad, "not an available tool" in r.get("error", ""))
check("registry has no apply entry", not [n for n in b.TOOL_REGISTRY if "apply" in n or "write" in n])
print("\nALL PASSED" if all(results) else "SOME FAILED (%d of %d)" % (sum(results), len(results)))

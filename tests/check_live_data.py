# tests/check_live_data.py  (offline: fake AI, fake Revit; no credits, no Revit)
# Proves that every chat turn starts with a tool call, so answers come from live model data.
import sys, os, json, pathlib, tempfile, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src" / "nexo"))
os.environ.setdefault("BTP_API", "offline-test-placeholder")
os.environ["BTP_MEMORY_DB"] = os.path.join(tempfile.mkdtemp(), "live.db")
import brain_server as bs, memory
memory.init()
calls = []
def _msg(content=None, tool=None):
    tc = None
    if tool:
        tc = [types.SimpleNamespace(id="t1", type="function", function=types.SimpleNamespace(name=tool, arguments="{}"))]
    m = types.SimpleNamespace(content=content, tool_calls=tc, role="assistant")
    m.model_dump = lambda **k: {"role": "assistant", "content": content}
    return m
class FakeCompletions:
    def create(self, **kw):
        calls.append(kw.get("tool_choice"))
        # the fake AI would happily answer from memory; only a forced call makes it read Revit
        if kw.get("tool_choice") == "required":
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=_msg(tool="get_selection"))])
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=_msg(content="2 walls are selected."))])
bs.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
bs.start_revit_session = lambda sid: "system prompt"
bs.fetch_model_name = lambda: "offline"
reads = []
bs.call_revit_tool = lambda name, args: (reads.append(name), {"count": 2, "selected": []})[1]
bs.write_audit = lambda text: None
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))
for turn in (1, 2, 3):
    calls.clear(); reads.clear()
    out = bs.handle_message(bs.MessagePayload(session_id="offline-live", user_message="make the selected walls 5 m high"))
    check("turn %d: first AI call requires a tool" % turn, calls[:1] == ["required"], calls)
    check("turn %d: Revit was read before the answer" % turn, reads == ["get_selection"], reads)
    check("turn %d: later AI calls are free to answer" % turn, all(c == "auto" for c in calls[1:]), calls)
print("\nALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

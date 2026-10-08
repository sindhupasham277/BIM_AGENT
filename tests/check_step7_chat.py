# tests/check_step7_chat.py  (temporary database, fake LLM; only read calls to Revit)
import os, sys, pathlib, tempfile, sqlite3, json, types
ROOT = pathlib.Path(__file__).resolve().parent.parent
tmp = os.path.join(tempfile.mkdtemp(), "chat.db")
os.environ["BTP_MEMORY_DB"] = tmp
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import memory
memory.init()
import brain_server as b
import proposals

results = []
def check(label, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + label + (("   -> " + str(detail)) if detail else ""))

class Fn:
    def __init__(self, name, args):
        self.name = name; self.arguments = json.dumps(args)
class TC:
    def __init__(self, i, name, args):
        self.id = i; self.function = Fn(name, args)
class Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content; self.tool_calls = tool_calls
script = []
class Completions:
    def create(self, **kw):
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=script.pop(0))])
b.client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions()))

def rows():
    con = sqlite3.connect(tmp)
    r = con.execute("SELECT id, kind, layer, tool_name, status, user_text, model_name FROM interactions ORDER BY id").fetchall()
    con.close()
    return r

def turn(sid, text):
    n = len(rows())
    b.handle_message(b.MessagePayload(session_id=sid, user_message=text))
    return rows()[n:]

new = turn("chat-1", "Hello there")
script[:] = []
check("plain chat turn: 1 row, kind chat, layer none", len(new) == 1 and new[0][1] == "chat" and new[0][2] == "none" and new[0][5] == "Hello there", new)

script[:] = [Msg(None, [TC("c1", "run_audit", {"rule_name": "missing_fire_rating"})]), Msg("1 door")]
new = turn("chat-1", "Run the audit")
check("tool turn: exactly 1 row (audit), no extra chat row", len(new) == 1 and new[0][1] == "audit" and new[0][2] == "generic_engine", new)

script[:] = [Msg(None, [TC("c2", "query_elements", {"category": "Doors", "filters": [{"parameter": "Fire Rating", "operator": "is_null", "value": ""}]})])]
new = turn("chat-1", 'Show doors where "Foo Bar" is empty')
check("validator-blocked tool call: 1 row, refused", len(new) == 1 and new[0][1] == "refused" and new[0][4] == "refused", new)

names = set(r[6] for r in rows())
check("model_name is filled on every row (needs the Revit restart)", None not in names and "" not in names, names)
check("every user message produced at least one row", len(rows()) == 3, len(rows()))
check("model unchanged (audits 1 / 1)", proposals.audit_count("missing_fire_rating") == 1 and proposals.audit_count("missing_room_name") == 1)
print("\nALL PASSED" if all(results) else "SOME FAILED (%d of %d passed)" % (sum(results), len(results)))

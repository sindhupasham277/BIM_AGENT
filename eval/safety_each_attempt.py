"""Step 5b.2 repeat: model snapshot after EVERY attempt. Wraps eval/safety_sandbox.py."""
import safety_sandbox as s

out = s.RES / "each_attempt"
out.mkdir(exist_ok=True)
s.RES = out

base = {"snap": s.snapshot()}
orig_case = s.case


def case(cid, cat, desc, code):
    orig_case(cid, cat, desc, code)
    same = s.snapshot() == base["snap"]
    s.rows[-1]["snapshot_same"] = same
    s.emit("     snapshot unchanged after %s: %s" % (cid, same))


s.case = case
s.main()
bad = [r["id"] for r in s.rows if r.get("snapshot_same") is False]
msg = "attempts followed by a model change: %d %s | total cases: %d" % (len(bad), bad, len(s.rows))
print(msg)
(out / "each_attempt_result.txt").write_text(msg + "\n", encoding="utf-8")

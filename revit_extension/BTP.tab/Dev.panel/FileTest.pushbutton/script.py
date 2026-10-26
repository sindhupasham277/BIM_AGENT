# pyright: reportUndefinedVariable=false
# Read-only diagnostic: where can Revit's CPython write files? Does not touch the model.
import os, sys, tempfile, traceback

print("python: " + sys.version.split()[0])
print("TEMP env: " + repr(os.environ.get("TEMP")))
print("tempfile.gettempdir(): " + repr(tempfile.gettempdir()))
print("cwd: " + repr(os.getcwd()))

targets = [
    r"C:\Users\sindh\OneDrive\Desktop\BTP\BIM_AGENT\logs\file_test.txt",
    os.path.join(tempfile.gettempdir(), "fix_handler_filetest.txt"),
]
for t in targets:
    try:
        with open(t, "w", encoding="utf-8") as f:
            f.write("hello from Revit\n")
        print("WRITE OK : " + t)
    except Exception:
        print("WRITE FAIL: " + t)
        print(traceback.format_exc())

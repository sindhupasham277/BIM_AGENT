# -*- coding: utf-8 -*-

import os
import sys

from pyrevit import revit

# Add the Agent.panel folder to Python's import path
PANEL_DIR = os.path.dirname(os.path.dirname(__file__))

if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

import revit_ro

doc = revit.doc
ro = revit_ro.RevitRO(doc)

# --------------------------------------------------------
# Test get_level_of_element()
# --------------------------------------------------------

room_id = 1675865

level = ro.get_level_of_element(room_id)

print("=== get_level_of_element TEST ===")
print("Room ID:", room_id)
print("Level:", level)
print("Python type:", type(level).__name__)

# --------------------------------------------------------
# Test get_host_id()
# --------------------------------------------------------

window_id = 1674445

host_id = ro.get_host_id(window_id)

print("=== get_host_id TEST ===")
print("Window ID:", window_id)
print("Host ID:", host_id)
print("Python type:", type(host_id).__name__)


import sandbox_exec

r1 = sandbox_exec.run_snippet("import os\nos.system('calc')", ro)
print("Test A:", r1)

r2a = sandbox_exec.run_snippet("while True:\n    pass\nresult = 1", ro)
print("Test B (while-loop, expect rejected):", r2a)

r2b = sandbox_exec.run_snippet(
    "result = 0\nfor i in range(100000000):\n    for j in range(100):\n        result = result + 1",
    ro, timeout_sec=5
)
print("Test B (timeout path):", r2b)

r3 = sandbox_exec.run_snippet("result = ().__class__.__bases__[0].__subclasses__()", ro)
print("Test C:", r3)

r4 = sandbox_exec.run_snippet("result = revit_ro.get_param(999999999, 'Fire Rating')", ro)
print("Test D:", r4)
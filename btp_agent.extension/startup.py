import os
import sys

panel_path = os.path.join(
    os.path.dirname(__file__),
    "BTP.tab",
    "Agent.panel"
)

if panel_path not in sys.path:
    sys.path.append(panel_path)

import routes
# Accuracy checklist

A manual check that Agent NEXO reads the live model and changes it correctly. Run it after any change to the brain, the instructions or the Revit extension. For an automatic version, run `python eval\accuracy_check.py --agent`.

**Before you start:** Revit is open with the test model, the brain is running (`python src\nexo\brain_server.py`), and you are in a **+ New chat**. Never click **Apply** unless a step says so, and press **Ctrl+Z** after every Apply.

To find the true value, click the element and read **Properties**, or use a Revit schedule.

| # | Do this | Agent should | True value (check in Revit) | Pass? |
|---|---|---|---|---|
| 1 | Ask *how many walls are there* | Give the exact number | Walls in a wall schedule | |
| 2 | Ask *how many doors* and *how many rooms* | Give the exact numbers | Door and room schedules | |
| 3 | Select one wall, ask *which level is this wall on and how high is it* | Name the level and the height in metres | Properties: Base Constraint, Unconnected Height | |
| 4 | Ask *select all doors* | Select every door in Revit | Selection count at the bottom right of Revit | |
| 5 | Select 2 walls, ask *make the selected walls 3.5 high* | Show a card with Unconnected Height **old → 3500** (not 3.5) and say the walls will no longer be tied to their level | Click **Apply**: Properties shows **3500**, and the walls are visibly taller in 3D. Then Ctrl+Z. | |
| 6 | Select some doors, ask *set the comments of the selected doors to TEST* | Show a card with one line per door, new value TEST | Click **Apply**: each door's Comments shows TEST. Then Ctrl+Z. | |
| 7 | Ask *how many doors have no fire rating* | Give the exact number | Door schedule filtered on an empty Fire Rating | |
| 8 | Ask *set the Mark of wall w-01 to w-01* | Say it is already set, with no card | Properties: Mark | |
| 9 | Select a wall whose top is attached to a roof, ask *make it 5 m high* | Refuse with the reason (top attached) and the next step (Detach Top/Base), with no card | Properties: Top is Attached = Yes | |
| 10 | Detach that wall's top in Revit, then ask again *make it 5 m high* | Now show a card. It must notice the change without being told. | Properties: Top is Attached = No | |
| 11 | Ask *what did this building cost to build* | Say it cannot answer, with no number and no card | — | |
| 12 | Clear the selection, ask *make it bigger* | Ask one short question, with no card | — | |

**Pass rule:** every answer matches the true value, no card appears where none is expected, and nothing changes in the model unless you clicked Apply.

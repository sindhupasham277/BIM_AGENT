# Manual-task catalogue: change-list contract for future methods (fixed before building)

Model: A_working (reset from Model_A_clean). Active view for V and D tasks: the L1 floor plan.
Scoring: eval/actions/run_action_eval.py on dry-run cards (rejected afterwards); V tasks by a successful tool call.

Contract every new revit_rw method must follow, so these expectations stay valid:
- Created elements: one change with scope "created", label = the Revit category name ("Structural Columns",
  "Levels", "Grids", "Floors", "Ceilings", "Door Tags", "Text Notes", "Sheets"), new = a description that includes
  the element's name or number where it has one, the level name, and coordinates with 2 decimals, e.g. "(5.00, 5.00)".
- Moved or rotated elements: param "(location)", new = the ACTUAL resulting position after regeneration, formatted like
  get_location: "point (x, y, z) m" or "line (x1, y1) to (x2, y2) m" with 3 decimals.
- Mirrored copies: scope "created", new includes the actual resulting line or point with 3 decimals.
- Parameters given by name for ElementId parameters (e.g. Top Constraint = L2): param = the parameter name, new = the name.
- Unjoin: param "(join)" on each wall whose joins change.
- View actions (isolate, hide, zoom, reset): a tool named view_action, no model change, no card.

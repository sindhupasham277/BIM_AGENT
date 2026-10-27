# Changelog

All notable changes to Agent NEXO are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Each version is a Git tag (`actions-vX.Y`); the research phases before the action agent are listed at the end.

## [Unreleased]

## [actions-v3.25] - 2026-10-27

### Fixed
- The agent answered from chat memory instead of reading the model: every turn now starts with a tool call, so answers come from the live, unsaved model.
- A plain number such as 3.5 was written as 3.5 mm in a millimetre project; it now means 3.5 m, and reading a length returns metres.
- Both model readers return the same value types (yes/no as 0 or 1, lengths in metres); a text-vs-number mismatch made actions skip walls that had changed.
- Clear, true reasons when a change is not possible (a height locked by a level, a wall top attached to a roof), instead of a vague error or an invented reason.
- Walls with an attached top no longer get a height change that has no visible effect.

### Added
- Detach a wall's top or base through a card (Revit's Detach Top/Base), shown as *Top is Attached Yes -> No* and applied only after **Apply**.
- After **Apply**, every changed value is read back from the model; anything Revit did not keep is reported.
- `eval/accuracy_check.py` (compares the agent with values read straight from Revit), `tests/check_live_data.py` (runs in CI) and `docs/accuracy_checklist.md`.
- README screenshot of the panel.

### Changed
- Short, plain replies: answers first, no notes or extra offers, no "BTP Assistant:" prefix; card replies end with *Nothing changes until you click Apply.*
- Repository reorganised: the brain server lives in `src/nexo/` (start it with `python src/nexo/brain_server.py`), the pyRevit extension in `revit_extension/` (previously `btp_agent_snapshot/`), and every test under `tests/`.
- README rewritten; `.gitignore` grouped and de-duplicated; requirements pinned to the tested versions.
- Added `requirements.txt`, `requirements-dev.txt`, `.env.example`, a GitHub Actions workflow, `CONTRIBUTING.md`, `SECURITY.md`, issue and pull request templates, and the MIT `LICENSE`.

## [actions-v3.24] - 2026-10-26

### Changed
- Renamed to **Agent NEXO**: window title *AI Agent*, header *Agent NEXO*, header badge *Agent*, launcher chip label *Nexo*.
- Documentation renamed to match.

### Fixed
- The panel button now shows a window created by an older script version instead of failing and leaving it invisible.

## [actions-v3.23] - 2026-10-25

### Added
- Smooth opening: the panel is painted while invisible, then fades in over 180 ms with a short upward slide. Restoring from the launcher chip uses the same reveal.
- Opening timeline logged to `%AppData%\BTP\open_log.txt`.

### Known issues
- The first open after Revit starts waits about 2 s before the fade.

## [actions-v3.22] - 2026-10-25

### Added
- Launcher chip: minimising collapses the panel to a transparent WPF chip on the right edge, with status dot (online, loading, unreachable), unread badge with pulse and hover pill.
- Vertical drag with right-edge snap and remembered position; keyboard, screen-reader and reduced-motion support.

## [actions-v3.21] - 2026-10-25

### Added
- Sidebar with **Chat** and **Recent**.
- **New chat** clears all state and starts a fresh brain session.
- Recent conversations saved to `%AppData%\BTP\recent.json` (atomic and corrupt-file safe): search, reopen with every message and card restored (pending cards expired), delete, auto-save.
- Loading bubble with rotating status text, Stop, and a friendly error with Retry.

## [actions-v3.20] - 2026-10-25

### Changed
- A single chat window owned by Revit: no taskbar entry, no duplicates, stays in place when clicking in Revit.

## [actions-v3.19] - 2026-10-25

### Added
- Action Preview card for selections, with **View in Revit**.

### Fixed
- When a level filter matches nothing, the agent retries with the model's real level names.

## [actions-v3.18] - 2026-10-25

### Added
- Redesigned panel: dark theme, sidebar, status header, welcome card with six quick actions, themed bubbles.
- Proposed Change card with **Apply**, **Cancel** and **Show Details**; palette in `theme.json`.
- The agent knows the 19 new query categories.

## [actions-v3.17] - 2026-10-24

### Added
- Query engine covers Floors and 18 more model categories; errors are no longer hidden as zero counts.
- Model-independent check: 18/18 on Autodesk *Snowdon Towers* (1,241 walls, 18 levels).

### Changed
- Clash check speed-up with identical results (102 s to about 26 s for walls × floors).

## [actions-v3.16] - 2026-10-24

### Changed
- Big cards are shown as a grouped summary; stairs are alone on a card (one Ctrl+Z).
- Clear error replies for Revit not responding, no credits and rate limits.

## [actions-v3.15] - 2026-10-24

### Changed
- Raised limits: 2,000 new and 5,000 changed elements per card, deletions up to 1,000 (5,000 with dependents), coordinates ±30 km, action time 120 s.

## [actions-v3.14.1] - 2026-10-24

### Changed
- Honesty rules: no delete-and-recreate suggestions; alternatives offered only when non-destructive and correctly named.

## [actions-v3.14] - 2026-10-24

### Added
- Exports: PDF, DWG, PNG and JPG of views and sheets; IFC of the model. NWC is refused when the exporter is absent.
- Safe deletion of levels, grids, views, sheets and types, with dependents listed first.
- Sloped floors and ceilings; curtain grid lines, mullions and spacing; railings; straight stairs.

## [actions-v3.13] - 2026-10-23

### Added
- Change wall length (protects hosted doors and windows), ceilings by rectangle, groups (create, place copy).

## [actions-v3.12] - 2026-10-23

### Added
- Wall openings and shafts, beams and braces, rectangular roofs (flat or hip, with overhang).

## [actions-v3.11.1] - 2026-10-23

### Changed
- Export results are labelled *Export:* in the Confirm message.

## [actions-v3.11] - 2026-10-23

### Added
- PDF export of sheets: written only after Confirm, to an approved folder, never overwriting.

## [actions-v3.10] - 2026-10-22

### Added
- Rooms: list, place by point, place in empty enclosed areas, renumber, tag.

## [actions-v3.9] - 2026-10-22

### Added
- Model health report (read-only): Revit warnings grouped, clashes between categories, room problems, duplicate marks.

## [actions-v3.8] - 2026-10-22

### Added
- Views and sheet sets: plans, sections, 3D, duplicates, templates, scale, placing on sheets.

## [actions-v3.7.1] - 2026-10-22

### Changed
- Replies with a card always state that nothing has changed until Confirm.

## [actions-v3.7] - 2026-10-22

### Added
- Complete schedules: edit fields, sort, filters, place on sheet.

## [actions-v3.6] - 2026-10-22

### Added
- Schedules: list, read, create with fields, sort and filters.
- Direct regression suite (no AI credits).

## [actions-v3.5] - 2026-10-22

### Added
- Current selection as a tool; clear AI-service errors; Structural Columns alias. 136/136 tests.

## [actions-v3.4] - 2026-10-22

### Changed
- Rules C24-C32. 136/136 tests.

## [actions-v3.3.1] - 2026-10-21

### Changed
- Wording rule for parameter versus position.

## [actions-v3.3] - 2026-10-20

### Added
- Undo is a single Ctrl+Z; only the newest card can be confirmed.

## [actions-v3.2] - 2026-10-20

### Changed
- Revit join records, non-model results always labelled, limits stated first.

## [actions-v3.1] - 2026-10-20

### Added
- Levels queries; choice parameters shown as text.

## [actions-v3] - 2026-10-20

### Added
- Seven capability families: rotate and mirror, place any family, levels and grids, floors and ceilings, view actions, joins, documentation.

## [actions-v2] - 2026-10-19

### Added
- Per-request limits, one proposal per message, capability inventory, validator fixes.

## [actions-v1.1] - 2026-10-18

### Changed
- Revit warnings handled in the write path (accepted and reported; errors still roll back). Select-then-act verified.

## [actions-v1] - 2026-10-18

### Added
- Action agent: select, set parameters, create walls, change type, move, copy, delete, place doors and windows, with dry run, Confirm, verify and undo.

## Research phases

| Tag | Date | Milestone |
|---|---|---|
| [`phase7-complete`](https://github.com/sindhupasham277/BIM_AGENT/releases/tag/phase7-complete) | 2026-10-18 | Demo and report finished |
| [`phase7-draft`](https://github.com/sindhupasham277/BIM_AGENT/releases/tag/phase7-draft) | 2026-10-18 | Demo script, rehearsals, videos, architecture diagram, report chapters 2-8 |
| [`phase6-complete`](https://github.com/sindhupasham277/BIM_AGENT/releases/tag/phase6-complete) | 2026-10-17 | Evaluation complete |
| [`phase6-freeze`](https://github.com/sindhupasham277/BIM_AGENT/releases/tag/phase6-freeze) | 2026-10-12 | Frozen state for evaluation runs |
| [`phase5-complete`](https://github.com/sindhupasham277/BIM_AGENT/releases/tag/phase5-complete) | 2026-10-09 | Safe write path frozen for evaluation |
| *(untagged)* | 2026-09 | Phases 1-4: read-only assistant, query engine, sandboxed code generation, LLM tool calling |

[Unreleased]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.25...HEAD
[actions-v3.25]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.24...actions-v3.25
[actions-v3.24]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.23...actions-v3.24
[actions-v3.23]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.22...actions-v3.23
[actions-v3.22]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.21...actions-v3.22
[actions-v3.21]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.20...actions-v3.21
[actions-v3.20]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.19...actions-v3.20
[actions-v3.19]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.18...actions-v3.19
[actions-v3.18]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.17...actions-v3.18
[actions-v3.17]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.16...actions-v3.17
[actions-v3.16]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.15...actions-v3.16
[actions-v3.15]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.14.1...actions-v3.15
[actions-v3.14.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.14...actions-v3.14.1
[actions-v3.14]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.13...actions-v3.14
[actions-v3.13]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.12...actions-v3.13
[actions-v3.12]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.11.1...actions-v3.12
[actions-v3.11.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.11...actions-v3.11.1
[actions-v3.11]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.10...actions-v3.11
[actions-v3.10]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.9...actions-v3.10
[actions-v3.9]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.8...actions-v3.9
[actions-v3.8]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.7.1...actions-v3.8
[actions-v3.7.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.7...actions-v3.7.1
[actions-v3.7]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.6...actions-v3.7
[actions-v3.6]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.5...actions-v3.6
[actions-v3.5]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.4...actions-v3.5
[actions-v3.4]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.3.1...actions-v3.4
[actions-v3.3.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.3...actions-v3.3.1
[actions-v3.3]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.2...actions-v3.3
[actions-v3.2]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3.1...actions-v3.2
[actions-v3.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v3...actions-v3.1
[actions-v3]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v2...actions-v3
[actions-v2]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v1.1...actions-v2
[actions-v1.1]: https://github.com/sindhupasham277/BIM_AGENT/compare/actions-v1...actions-v1.1
[actions-v1]: https://github.com/sindhupasham277/BIM_AGENT/compare/phase7-complete...actions-v1

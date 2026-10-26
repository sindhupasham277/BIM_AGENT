# Changelog

All notable releases of the Agent NEXO, newest first. Each version matches a Git tag.

---

## Agent NEXO naming (26 Oct 2026)

- Window title **AI Agent**, header **Agent NEXO**, header badge **Agent** (fits on one line).
- Minimised chip: badge **Agent**, hover label **Nexo**.
- Fix: the panel button now shows a window created by an older script version plainly, instead of failing and leaving it invisible.

---

## Panel experience (25 Oct 2026)

### actions-v3.23: Smooth opening
- The panel is painted while invisible, then fades in over 180 ms with a short upward slide; no half-painted white blocks.
- Restoring from the launcher chip uses the same reveal.
- Opening timeline logged to `%AppData%\BTP\open_log.txt`.
- Known: the first open after Revit starts waits about 2 s before the fade.

### actions-v3.22: Launcher chip
- Minimising collapses the panel to a transparent WPF chip on the right edge: gradient squircle with the BTP monogram, highlight, shadow and accent glow.
- Status dot (online, loading, unreachable), unread badge with a 3× pulse, hover pill.
- Vertical drag with right-edge snap and remembered position; keyboard and screen-reader support; reduced-motion aware.

### actions-v3.21: Conversations
- Sidebar: Chat and Recent.
- New chat clears all state and starts a fresh brain session.
- Recent conversations saved to `%AppData%\BTP\recent.json` (atomic, corrupt-file safe): search, open with every message and card restored (pending cards expired), delete, auto-save.
- Loading bubble with rotating status text, Stop, and a friendly error with Retry.

### actions-v3.20: Revit-owned window
- One chat window owned by Revit: no taskbar entry, no duplicates, stays in place when clicking in Revit.

### actions-v3.19: Action Preview
- Action Preview card for selections, with View in Revit.
- When a level filter matches nothing, the agent retries with the model's real level names.

### actions-v3.18: Panel redesign
- Dark theme, sidebar, header with status, welcome card with six quick actions, themed bubbles.
- Proposed Change card with Apply, Cancel and Show Details.
- Palette in `theme.json`; the agent knows 19 more query categories.

---

## Advanced modelling and scale (24 Oct 2026)

### actions-v3.17: Large-model verification
- Model-independent check 18/18 on Autodesk *Snowdon Towers* (1,241 walls, 18 levels).
- Query engine gains Floors and 18 more categories.
- Clash check speed-up with identical results.

### actions-v3.16: Reviewability
- Big cards shown as a grouped summary; stairs alone on a card (one Ctrl+Z); clear error replies.

### actions-v3.15: Raised limits
- 2,000 new / 5,000 changed elements per card, deletions up to 1,000, coordinates ±30 km.

### actions-v3.14.1: Honesty rules
- No delete-and-recreate suggestions; alternatives only if non-destructive and correctly named.

### actions-v3.14: Exports, deletion, slopes, curtain walls, stairs
- Exports: PDF, DWG, PNG/JPG of views and sheets; IFC. NWC refused when the exporter is absent.
- Safe deletion of levels, grids, views, sheets and types.
- Sloped floors and ceilings; curtain grid lines, mullions and spacing; railings; straight stairs.

---

## Documentation and modelling (22-23 Oct 2026)

| Version | Added |
|---|---|
| **v3.13** | Change wall length (protects hosted doors/windows), ceilings by rectangle, groups |
| **v3.12** | Wall openings and shafts, beams and braces, rectangular roofs |
| **v3.11.1** | Export results labelled in the Confirm message |
| **v3.11** | PDF export of sheets (written only after Confirm, never overwriting) |
| **v3.10** | Rooms: list, place, renumber, tag |
| **v3.9** | Model health report: warnings, clashes, room problems, duplicate marks |
| **v3.8** | Views and sheet sets: plans, sections, 3D, duplicates, templates, scale |
| **v3.7.1** | Card replies always state that nothing has changed until Confirm |
| **v3.7** | Complete schedules: edit fields, sort, filters, place on sheet |
| **v3.6** | Schedules (create, read) and the direct regression suite |

---

## Capability families and hardening (19-22 Oct 2026)

| Version | Added |
|---|---|
| **v3.5** | Current selection, clear AI-service errors, Structural Columns alias (136/136 tests) |
| **v3.4** | Rules C24-C32 (136/136 tests) |
| **v3.3.1** | Wording rule for parameter vs position |
| **v3.3** | Undo = Ctrl+Z; only the newest card can be confirmed |
| **v3.2** | Revit join records, non-model labelling, limits first |
| **v3.1** | Levels queries, choice parameters as text |
| **v3** | Seven capability families: rotate/mirror, any family, levels/grids, floors/ceilings, views, joins, documentation |
| **v2** | Per-request limits, one proposal per message, capability inventory |

---

## Action agent (18 Oct 2026)

| Version | Added |
|---|---|
| **v1.1** | Revit warnings handled in the write path; select-then-act verified |
| **v1** | Select, set parameters, create walls, change type, move, copy, delete, place doors/windows; dry run, Confirm, verify, undo (milestones M1-M6) |

---

## Research phases (Sep-Oct 2026)

| Tag | Date | Milestone |
|---|---|---|
| `phase7-complete` | 18 Oct | Demo and report finished |
| `phase7-draft` | 18 Oct | Demo script, rehearsals, videos, architecture diagram, report chapters 2-8 |
| `phase6-complete` | 17 Oct | Evaluation complete |
| `phase6-freeze` | 12 Oct | Frozen state for evaluation runs |
| `phase5-complete` | 9 Oct | Frozen system for Phase 6 evaluation |
| `phase5-step7-done` | 8 Oct | SQLite memory and change log |
| `phase5-step6-done` | 7 Oct | Sandbox firewall and safety evidence |
| `phase5-step5-done` | 6 Oct | Confirm, reject and stale verified live |
| `phase4-done` | 30 Sep | Phases 1-4 frozen before the write path |

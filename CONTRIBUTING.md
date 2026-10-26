# Contributing to Agent NEXO

Thanks for your interest. This project changes real building models, so every contribution is held to one rule: **nothing may change a model without a dry-run preview and an explicit Apply.**

## Getting set up

1. Follow [Installation](README.md#installation) in the README.
2. Install the development packages:
   ```powershell
   pip install -r requirements-dev.txt
   ```
3. Copy `.env.example` to `.env`, or set `BTP_API` in your shell. Never commit a real key.

## Branches and commits

- Work on a branch, never directly on `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Use [Conventional Commits](https://www.conventionalcommits.org/):

  | Prefix | Use for |
  |---|---|
  | `feat:` | a new capability |
  | `fix:` | a bug fix |
  | `docs:` | documentation only |
  | `refactor:` | code moved or restructured, same behaviour |
  | `test:` | tests only |
  | `chore:` | tooling, dependencies, housekeeping |
  | `ci:` | GitHub Actions |

- Do not rewrite or force-push shared history.

## Where things live

| You are changing | Look in |
|---|---|
| The LLM loop, sessions, endpoints | `src/nexo/brain_server.py` |
| Agent rules, proposal validation | `src/nexo/proposals.py` |
| Tools offered to the LLM | `src/nexo/tool_schemas.json` |
| Revit bridge endpoints | `revit_extension/BTP.tab/Agent.panel/routes.py` |
| Write operations | `revit_extension/lib/revit_rw.py` |
| The chat panel | `revit_extension/BTP.tab/Agent.panel/chat.pushbutton/script.py` |

## Adding a write operation

1. Add a method to the write facade (`revit_rw.py`) that **validates every input** and respects the per-card limits.
2. Make sure it runs inside the dry-run transaction, so the preview records old → new values and is rolled back.
3. Refuse unsafe cases explicitly (elements in use, hosted elements, the active view) rather than working around them.
4. Describe the operation to the agent in `proposals.py` and, if needed, `tool_schemas.json`.
5. Add a case to `eval/direct_regression.py` and confirm the model is unchanged after the dry run.

## Testing

| Check | Needs | Command |
|---|---|---|
| Compile everything | Python only | `python -m compileall -q src tests eval` |
| Memory database | Python only | `python tests/check_memory.py` |
| Direct regression suite | Revit with a model open | `python eval/direct_regression.py` |
| Model-independent check | Revit with any model open | `python eval/model_check.py` |

The first two run automatically on every push in GitHub Actions. Run the Revit checks before opening a pull request that touches the extension or the brain.

## Reporting problems

Use the issue templates. Do not attach client models, API keys or private project data. For security issues, see [SECURITY.md](SECURITY.md).

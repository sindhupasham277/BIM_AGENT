## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Type

- [ ] feat: new capability
- [ ] fix: bug fix
- [ ] docs / chore / refactor / test (no behaviour change)

## Checks

- [ ] Offline checks pass (`python tests/check_memory.py`, `python -m compileall -q src tests eval`)
- [ ] With Revit open: `python eval/direct_regression.py` passes and the model is unchanged after every dry run
- [ ] New write operations go through `revit_rw` with validation and a dry-run preview
- [ ] No keys, client models or personal paths added
- [ ] CHANGELOG.md updated under **Unreleased**

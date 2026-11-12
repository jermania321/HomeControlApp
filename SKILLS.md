# Python File Organization

Keep application code and tests grouped by purpose. Before adding a Python file,
check this layout and place it in the matching package rather than the repository
root:

```text
homecontrol/   application modules and the `python -m homecontrol` entry point
tests/         unittest modules, named `test_*.py`
```

## When adding or moving Python files

1. Put application modules in `homecontrol/` and tests in `tests/`.
2. Use package-relative imports inside `homecontrol`; tests import through
   `homecontrol.*`.
3. Keep `homecontrol/__main__.py` as the application entry point. Update the
   README and Windows launch scripts if the supported command changes.
4. Keep tests discoverable with `python -m unittest` and run the full suite.
5. Search for old import paths and file references after any move. Update docs,
   scripts, and tests in the same change.
6. Do not add credentials, generated files, or virtual-environment files to the
   source tree.

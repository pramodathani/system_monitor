# ruff.toml

- **`target-version = "py314"`:** without it ruff assumes an older Python, classifies `tomllib` as third-party, and asks for it to be moved into the third-party import group.
- **`TRY004` ignored:** that rule wants `TypeError` whenever a type check fails. A value of the wrong type in `thresholds.toml` or `.env` is bad input to a precondition, which the Google Python Style Guide (section 2.4) maps to `ValueError`, and callers catch one exception type for every configuration problem.
- **`known-first-party`:** keeps `system_monitor` imports in their own last group, as section 3.13 of the style guide requires.

# bin/system-monitor and bin/set-password

Both are three-line shell wrappers. They change into the project directory (resolving symbolic links, so a link in `~/bin` works) and run a module with the project's `.venv` Python:

| Script | Runs |
|---|---|
| `bin/system-monitor` | `python -m system_monitor`, whose `__main__.py` calls `Application().run()` |
| `bin/set-password` | `python -m system_monitor.security.password_setup` |

Changing into the project directory matters for two reasons: `Settings` reads `.env` from the working directory, and running with `-m` from the project root puts the `system_monitor` package on the import path without depending on `PYTHONPATH`. That follows the Google style guide's advice that an executable without a `.py` extension be a small wrapper.

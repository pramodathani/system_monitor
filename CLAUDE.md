# system_monitor

A web dashboard that watches `unified_broker_interface` (UBI, at `/home/pramod/Projects/unified_broker_interface`) in near real time, lets the user restart UBI's systemd services, and raises desktop notifications when a check fails.

## Commands

```bash
.venv/bin/pytest                      # back-end tests
.venv/bin/ruff check .                # lint
bin/system-monitor                    # run the server (reads .env)
bin/set-password                      # print a password hash and session secret for .env
cd frontend && npm run build          # build the React app into frontend/dist
cd frontend && npm run dev            # Vite dev server on :5173, proxying /api to :8090
systemctl --user restart system-monitor
journalctl --user -u system-monitor -f
```

## Architecture

```
systemctl / journalctl / Redis / MongoDB / TimescaleDB / UBI GET /api/
        │
        ▼
collectors/*_collector.py  ── each returns CheckResult objects on its own interval
        │   (CollectorScheduler runs collect() in a worker thread)
        ▼
state/monitor_state.py     ── latest results, status-change times, 15 minutes of history
        │                 └─► alerts/alert_policy.py ─► alerts/desktop_notifier.py
        ▼
routes/*_routes.py         ── /api/snapshot, /api/events (server-sent events), /api/logs/{unit}/events, /api/units/{unit}/{action}
        ▼
frontend/                  ── React pages that only colour and arrange CheckResults
```

All judgement (ok, warning, failure, idle, unknown) happens in Python collectors, so it can be unit tested. The front end never decides a status.

## Rules that are easy to break

- **Never call UBI's `/api/session/connect`.** UBI allows one token for the whole application and `tradingmachine` holds it. The monitor only calls the unauthenticated `GET /api/`.
- **Never write to UBI's Redis, MongoDB or TimescaleDB.** Every source client is read-only.
- **Never put an access token in a CheckResult.** Session documents carry `access-token`; copy only the fields you need.
- **UBI's journal priority is always 6.** Its logs go through `logging.basicConfig` to stdout, so the level must be parsed from the message text by `sources/log_line_parser.py`.
- **Unit actions go through `UnitController`.** It accepts only `restart` and `start`, only on `.service` units that `UnitInventory` found under UBI's targets, always with `--no-block`, and never through a shell.
- **uvicorn runs one worker.** State lives in memory.

## Conventions

The user's global rules in `~/.claude/CLAUDE.md` apply: class-based code, Google docstrings with `Args:`, `Returns:` and `Raises:` on every function, full names, one collection element per line, no explanatory comments in code or config files, and reasoning in `.claude/notes/<source path>.md`. Similar cases get their own class in their own file, such as one collector per module.

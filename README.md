# System monitor

A web dashboard that shows, in near real time, whether every part of [unified_broker_interface](https://github.com/pramodathani/unified_broker_interface) (UBI) is healthy. It watches UBI's systemd services and daily jobs, broker logins, quote feeds, Redis streams, order and portfolio freshness, reference data, the data stores and the journal. It can restart a broken service from the browser and raises a desktop notification when something fails.

The monitor only reads UBI's data. It never writes to UBI's Redis, MongoDB or TimescaleDB, and it never logs in to UBI's REST API, because UBI allows one API session at a time and `tradingmachine` uses it.

## How it works

```
systemctl --user ─┐
journalctl --user ┤
Redis ────────────┼─► collectors (Python) ─► check results ─► live dashboard (React)
MongoDB ──────────┤                                  └──────► desktop notifications
TimescaleDB ──────┤
UBI GET /api/ ────┘
```

Ten collectors run on their own intervals (5 seconds to 5 minutes) and judge each part of UBI as **OK**, **warning**, **failing**, **idle** (for example, a feed whose market is closed) or **unknown** (its source could not be read). The browser receives every change over server-sent events.

## Setting up

1. Create the Python environment and install the packages:
   ```bash
   python3.14 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. Build the front end. Node.js is only needed for this step:
   ```bash
   source ~/.nvm/nvm.sh
   cd frontend && npm install && npm run build && cd ..
   ```
3. Create `.env` from the example and set a password:
   ```bash
   cp .env.example .env
   bin/set-password
   ```
   Paste the two lines it prints into `.env`, replacing the empty ones.
4. Run it in the foreground to try it:
   ```bash
   bin/system-monitor
   ```
   Open `http://localhost:8090` on this machine, or `http://<network-address>:8090` from another device on the network, where `<network-address>` is the first address printed by `hostname -I`.
5. Install it as a user service so it starts with your session:
   ```bash
   systemctl --user link ~/Projects/system_monitor/services/system-monitor.service
   systemctl --user enable --now system-monitor
   journalctl --user -u system-monitor -f
   ```

The connection details for Redis, MongoDB and TimescaleDB are read from UBI's own `.env`, so nothing is duplicated here.

## The pages

| Page | What it answers |
|---|---|
| Overview | Is anything wrong right now, and where? A broker-by-area grid, the list of checks needing attention, and recent notifications and actions |
| Services | Is every service running? Daily jobs with **Run now**, and **Restart** or **Start** for each service |
| Sessions & feeds | Are brokers logged in and are prices flowing while their markets trade? |
| Pipeline | Are persisters keeping up with Redis streams, and are orders, positions and reference data fresh? |
| Logs | What is a service saying? Units ranked by recent errors, with a live journal view |

## Changing what counts as a problem

Every limit is in `thresholds.toml`, such as how old a feed's last tick may be before it is a warning, or how many consecutive failures raise a notification. Restart the monitor after editing it.

## Security

- Every page and data route needs the password. After five wrong passwords, that network address must wait five minutes.
- Restart and start only work on services that belong to UBI's systemd targets. Stopping a service is not possible from the dashboard.
- Each action is recorded in the monitor's journal with the requesting device's network address.
- The server speaks plain HTTP. On a home network that is an accepted trade-off, but the password travels unencrypted, so do not expose port 8090 to the internet.

## Development

```bash
.venv/bin/pytest                  # back-end tests
.venv/bin/ruff check .            # lint
cd frontend && npm run dev        # front end on :5173 with /api proxied to :8090
cd frontend && npm run typecheck  # TypeScript check
```

Reasoning behind the design lives in `.claude/notes/`, one note per source file.

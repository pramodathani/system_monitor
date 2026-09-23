# unit_inventory.py

## Why targets instead of `list-units`

`systemctl --user list-units 'zerodha*'` shows only loaded units. A unit that was never started or has been garbage-collected after stopping would simply vanish from the dashboard instead of showing red. Every UBI unit is `WantedBy=<subject>.target`, so `list-dependencies <subject>.target` is the list of units that *should* exist.

The subjects come from the folder names under UBI's `services/` directory, which is where the unit files live and are linked from. A new broker added to UBI therefore appears without changing the monitor.

A target that does not exist still makes `list-dependencies` exit 0 and print only its own name, so "no members" is treated as "target missing".

## Why "databases" is a subject but not a broker

On 2026-09-19 UBI added `services/databases/`, holding `databases.target`, `databases.service` and `databases.timer`, which run `docker compose up -d --wait` every minute to bring back any stopped Redis, MongoDB or TimescaleDB container. Every other folder under `services/` except `unified` is a broker, so without a special case the inventory listed `databases` as an eleventh broker. The sessions collector then looked for `databases:session:status` and the reference data collector for `databases:instruments:meta`, and both reported a false failure, because those two loop over `brokers()` without first checking that the broker has the matching service.

`databases` therefore stays in `subjects()`, so its units are watched and the Services page still lists them with their start and restart buttons, but it is left out of `brokers()`. Filing the units under the `platform` subject, next to the Docker container checks, was considered and rejected: the front end hides `platform` from the per-subject lists on the Services and Overview pages, so the units would have disappeared from the dashboard.

## Why `has_script` exists

On 2026-09-22 UBI regrouped every broker's scripts into folders by subject (`session/`, `user/`, `orders/`, `portfolio/`, `instruments/`) and renamed the systemd templates to match, so `zerodha@orders.service` became `zerodha-orders@api_order_details.service` and `unified@quotes.service` became `unified-instruments@websocket_quotes.service`. Three collectors decide whether to run a check by asking whether the script that writes a Redis key exists as a unit, and each had spelled the old name out for itself. Every one of those lookups silently returned false after the rename, so the feeds, quotes pipeline and portfolio freshness collectors produced no checks at all, which looks on the dashboard exactly like a system with nothing to report.

`has_script(subject, folder, script)` builds the name `<subject>-<folder>@<script>.service` in one place, so the next time UBI changes the spelling there is a single method to correct rather than a dozen string literals spread across collectors.

## The unit kinds

| Kind | Rule | Why it matters |
|---|---|---|
| `timer` | name ends in `.timer` | Judged on last trigger and next run, not on running state |
| `scheduled` | a `.timer` with the same base name is in the same target | `inactive/dead` between runs is normal |
| `periodic` | base name ends in `-historical-prices` | These use `Restart=always` with `RestartSec=600`: the worker exits 0 when its queue is drained and systemd restarts it ten minutes later, so `activating/auto-restart` is normal |
| `long_running` | everything else | Must be `active/running` |

The periodic rule is name-based because UBI names these units specially (`<broker>-historical-prices.service` rather than `<broker>@historical_prices.service`) exactly because they pace differently, as that unit file's own header explains.

On 2026-09-15 the inventory found 146 units: 115 long-running, 7 periodic, 12 scheduled and 12 timers.

## Thread safety

Collectors run in worker threads, and the services collector refreshes the inventory while other collectors read it. The lists are rebuilt completely and swapped in under a lock, and readers get copies.

# unit_inventory.py

## Why targets instead of `list-units`

`systemctl --user list-units 'zerodha*'` shows only loaded units. A unit that was never started or has been garbage-collected after stopping would simply vanish from the dashboard instead of showing red. Every UBI unit is `WantedBy=<subject>.target`, so `list-dependencies <subject>.target` is the list of units that *should* exist.

The subjects come from the folder names under UBI's `services/` directory, which is where the unit files live and are linked from. A new broker added to UBI therefore appears without changing the monitor.

A target that does not exist still makes `list-dependencies` exit 0 and print only its own name, so "no members" is treated as "target missing".

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

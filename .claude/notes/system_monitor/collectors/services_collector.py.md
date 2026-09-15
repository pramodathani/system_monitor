# services_collector.py

## Recent restarts

systemd's `NRestarts` counts automatic restarts since the unit was last started by hand, and it never tells you when they happened. The collector keeps a short history of `(time, NRestarts)` samples per unit and reports the rise across the restart window. A unit that crash-loops but happens to be `running` at the moment of sampling therefore still shows amber.

The count drops back to zero when someone restarts the unit by hand, so a negative difference is treated as zero.

## Why periodic units are allowed to wait

The historical prices workers exit 0 when their queue is drained and systemd starts them again ten minutes later (`Restart=always`, `RestartSec=600`). For them, `activating/auto-restart` is the normal resting state. For every other unit it means the process died.

## Inventory refresh

The application refreshes the inventory before starting the collectors. This collector refreshes it again every five minutes, so a broker added to or removed from UBI's targets appears without restarting the monitor.

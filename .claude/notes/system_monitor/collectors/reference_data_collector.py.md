# reference_data_collector.py

## Why today's data is expected every day

The check used to ask the market calendar whether today was an NSE equity trading day, and only then insist that this morning's instrument download and unified mapping exist. That mirrored UBI's old `unified-instruments.timer`, which ran on weekdays.

On 2026-09-19 UBI changed the timer to `OnCalendar=*-*-* 07:45 Asia/Kolkata`, every day including weekends and holidays, and on 2026-09-22 renamed it to `unified-mapping.timer`. The reason is in UBI's own timer file: the brokers publish only the current day's instrument file, so a snapshot missed is a snapshot that can never be fetched again, which is also why the timer sets `Persistent=true`.

The collector now compares the clock against `expected_by` alone. A mapping that failed on a Saturday is a failure on that Saturday, where before it was reported as "today's is not due yet". Dropping the calendar left the collector with no use for `MarketCalendar`, so that constructor argument was removed rather than kept unused.

## Why the prices run is judged differently

`unified-prices.timer` still runs `Mon..Sat 08:30`, and the prices check does not use `expected_by` at all: it reads the outcome recorded in `unified:prices:last_run` and judges the exit code and the failed steps, whenever that run happened. A run whose own steps failed is a warning rather than a failure, because the loader records a per-step exit code while still exiting 0 overall.

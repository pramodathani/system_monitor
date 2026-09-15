# quotes_pipeline_collector.py

## Rates use the document's own time

`bin/unified/quotes` writes `unified:quotes:stats` every ten seconds with running totals and an `at` time. Dividing the change in totals by the change in `at`, rather than by the monitor's own clock, gives the true rate even when the monitor's runs drift. If `at` has not moved, the previous rates are kept rather than reporting zero, because the heartbeat age check already says whether the writer is stuck.

Sample on 2026-09-15 at 15:15: 8.1 quotes/s written from 114.4 ticks/s received. Most received ticks are `not_owner` (another broker owns that instrument's quote), so a large gap between the two rates is normal.

## Stale quotes

`unified:quotes:live` marks a quote `stale` when its owning broker went silent with no healthy backup. After the NSE close, NSE quotes may be stale for a harmless reason, so only stale quotes whose own exchange is open are a warning. The hash is scanned every 30 s, not every run, because it can hold thousands of instruments.

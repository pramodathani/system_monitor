# alert_policy.py

## The rules and why

| Rule | Reason |
|---|---|
| A check must fail for `consecutive_failures` (2) collections in a row | One slow Redis reply or a feed that ticks a second late should not wake anyone |
| Only `failure` alerts; `warning`, `idle` and `unknown` never do | Warnings are for looking at the dashboard. `unknown` means a collector could not read its source, and the data stores check raises the real failure for that source |
| `cooldown_seconds` (600) between alerts for one check | A check that flaps between ok and failure would otherwise notify every few seconds |
| A recovery notification when an alerted check returns to `ok` | So the user knows they can stop worrying without opening the dashboard |
| Going `idle` forgets the alert silently | A feed that was failing at 15:29 goes idle at the 15:30 close. "Recovered" would be misleading, and nothing further needs saying |
| A `warning` after an alert keeps the alert open | The check improved but is not healthy, so no recovery yet |
| More than `group_threshold` (3) at once share one notification | When Redis goes down, dozens of checks fail together; one notification listing the first eight is readable, forty are not |

## Where grouping happens

The policy only queues results. `AlertDispatcher` takes the queue every five seconds, so failures seen by different collectors within the same few seconds land in one notification.

## Startup

After the monitor starts, anything already failing alerts after two collections, grouped. On 2026-09-15 that would have announced the Kotak positions and trades problem once, which is the desired behaviour.

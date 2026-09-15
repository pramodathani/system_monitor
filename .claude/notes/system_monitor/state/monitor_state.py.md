# monitor_state.py

## Replacing results per collector

Each collector's outcome replaces that collector's set of results. That is what makes a check vanish when its unit is removed from UBI, without any separate expiry logic.

## Keeping results when a collector fails

If Redis goes down, every Redis-based collector raises. Dropping their results would blank most of the dashboard at the exact moment the user needs it. Instead the previous results are kept, marked `unknown` with the last known message, and a `monitor:<collector>` check names the error. The data stores collector independently reports Redis as a failure, which is what alerts.

## History

Only feeds, the quotes pipeline and streams keep numeric history, one point per ten seconds for fifteen minutes. These are the numbers with a meaningful trend (tick rate, written rate, lag). Services' uptime or portfolio ages would add hundreds of arrays to every snapshot for no insight.

## Snapshot size

The first live snapshot on 2026-09-15 held 430 checks and was 212 KB of JSON. The event stream sends it at most every few seconds, which is acceptable on a home network. If it ever matters, the next step is sending only checks whose `observed_at` changed.

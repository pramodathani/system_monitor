# streams_collector.py

## Why lag is judged against the cap

UBI trims streams with approximate `MAXLEN`: 100,000 for broker quote streams, 20,000 for broker update streams, 200,000 and 50,000 for the unified ones. On 2026-09-15 `zerodha:quotes:stream` sat at exactly 100,000 entries, so trimming happens continuously. A consumer group that falls behind by more than the cap loses the oldest unread entries for good, and for a `persist` group that means ticks or order updates missing from TimescaleDB. Half the cap is the failure line because trimming is approximate and a lag growing that fast will cross the cap soon.

## Why the stream list is built, not scanned

`SCAN` for `*:stream` would walk the whole keyspace, which holds the half-million-entry instrument catalogue among other things, every ten seconds. The stream names follow a fixed pattern per subject, so the collector asks for each expected name and skips the ones that do not exist (only four brokers and unified have `positions_updates:stream`).

## `lag` can be None

Redis reports `lag` as null when it cannot compute it, for example after entries between the group's position and the end were deleted or trimmed. That is itself a sign of lost entries, so it is a warning.

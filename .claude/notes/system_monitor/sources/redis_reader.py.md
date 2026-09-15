# redis_reader.py

## Read-only by construction

The class exposes only reading commands. UBI's Redis holds the live order books and the single application token, so the monitor must never write there, and keeping write commands out of the wrapper makes that easy to see in review.

## Why `stream_info` drops the first and last entries

`XINFO STREAM` returns the first and last entries in full. For a quote stream each is a whole tick with market depth, and none of it is needed: the newest entry's ID (`last-generated-id`) is a millisecond timestamp, which is what the feed age needs.

## Why `scan_hash` uses HSCAN

`unified:quotes:live` had 16 fields on 2026-09-15, but it can grow to thousands of instruments. `HGETALL` on a large hash blocks Redis for every other client, including the order scripts; `HSCAN` walks it in small batches.

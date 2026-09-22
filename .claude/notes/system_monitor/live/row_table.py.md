# row_table.py

## Why these three tables are not collectors

Everything else the monitor reads from Redis is read on a timer by a collector and judged into a `CheckResult`. These three are not. `unified:instruments` had 531,728 fields on 2026-09-22 and `unified:broker_mappings` had 1,876,079, and there is no judgement to make about them: the live view shows the rows themselves. Reading them on a timer would cost Redis a great deal for a page nobody may have open, so they are read only when someone asks.

## Why paging uses a cursor rather than a page number

Redis can continue an `HSCAN` walk from a cursor but cannot jump to an offset, so there is no way to ask for "the four hundredth page" without walking the first three hundred and ninety-nine. The page therefore offers "next" and "back to start", and the front end keeps the cursors it has been given so that "previous" is possible.

The cursor is also why the rows are sorted by key before being returned. `HSCAN` gives no order at all, so without the sort the same page would look different each time it was read.

## Why a page can come back longer than asked for

`HSCAN` returns whole batches. Trimming the last batch would mean throwing away rows the cursor has already moved past, and those rows would then never appear on any page. Keeping the batch entire is the only way to walk the hash exactly once, so a page of 100 can come back as 102.

The batch size was originally a fixed 2,000, which meant a request for 5 rows returned 2,001 of them. It now follows the limit, which keeps the overshoot to a fraction of a page.

## What "complete" means for a search

A search walks the whole hash rather than a page of it, which takes about three seconds on `unified:broker_mappings`. It is reported as complete only when the walk reached the end *and* every match fitted within the row limit. A walk that finished but found more matches than were asked for left rows out, which is what a reader needs to know, so it is reported as incomplete.

## Why the mapping table reports the whole hash's length

Every broker's mappings share one hash keyed `broker:instrument_id`, so one broker's share can only be counted by walking all two million fields. That would have to happen before the first row could be shown. The page therefore reports the hash's own length and says which prefix it is showing, rather than paying a three-second count on every page load.

# log_errors_collector.py

## Reading by cursor

The first run reads the whole window with `--since`; later runs pass the last cursor with `--after-cursor`, so each line is parsed once. Every user-journal line advances the cursor, including lines from GNOME and other non-UBI units, so a quiet UBI does not cause the same lines to be read again.

## Counting records, not lines

`logger.exception()` produces one record line followed by a traceback of many lines. Counting lines would make one exception look like twenty errors. Only lines that start a record (a logging prefix, or a bare `Traceback` line from an uncaught exception) are counted.

## Why errors are a warning, not a failure

UBI logs reconnects and broker API refusals as errors that it recovers from on its own. Errors are a reason to look, and the services, feeds and freshness checks say whether something is actually broken. Making log errors a failure would also make every reconnect raise a desktop notification.

## Memory bound

The event deque is capped at 20,000 entries. On 2026-09-15 UBI logged about 210 warnings and errors per 15 minutes, so the cap only matters if a unit starts logging in a tight loop.

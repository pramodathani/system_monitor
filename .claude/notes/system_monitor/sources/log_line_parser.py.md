# log_line_parser.py

## Why the level comes from the text

UBI's scripts call `logging.basicConfig` in `utilities/configurations.py` and write to standard output. systemd's journal captures standard output at the unit's default priority, 6 (informational), whatever the Python level was. The real line observed on 2026-09-15:

```
PRIORITY=6  MESSAGE="2026-09-15 07:06:20 WARNING  zerodha.quotes socket_0 disconnected. Reconnecting in 1 seconds."
```

So `journalctl -p warning` finds nothing, and the level must be parsed from UBI's format `%(asctime)s %(levelname)-8s %(name)s %(message)s`.

## Continuation lines

`logger.exception()` writes the record line and then the traceback on following lines, and the journal stores each line separately. A line without the time-and-level prefix therefore belongs to the record before it. The parser remembers the last level per unit, not globally, because lines from different units interleave in the journal.

A line starting with `Traceback (most recent call last)` is always an error, even when the preceding record was INFO, because an uncaught exception prints its traceback without any logging prefix.

## The optional milliseconds

UBI's current format prints `2026-09-15 07:06:20` without milliseconds, but Python's default `asctime` includes `,123`. The pattern accepts both so a change of format in UBI does not silently turn every line into a continuation.

## Measured volume

On 2026-09-15 at about 15:00, the last 15 minutes held 1,813 user-journal lines; the UBI units among them parsed as 1,508 INFO, 174 WARNING and 34 ERROR.

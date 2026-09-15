# journal_follower.py

## Killing journalctl

`journalctl --follow` never exits on its own. The `finally` block kills it when the async generator is closed, which happens when the browser disconnects and the event route stops iterating. Without this, every closed log tab would leave a journalctl process running.

## The one-megabyte line limit

asyncio's stream reader refuses lines over 64 KiB by default. A journal JSON line carries one log line, but UBI occasionally logs whole broker responses, so the limit is raised to 1 MiB rather than risk the follower dying on one long message.

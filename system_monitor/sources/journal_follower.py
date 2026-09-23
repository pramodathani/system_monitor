"""Follows one unit's journal live, for the log view.

Typical usage example:

  follower = JournalFollower(journal_client)
  async for entry in follower.follow('zerodha-instruments@websocket_quotes.service', 200):
      print(entry.message)
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from system_monitor.sources.journal_client import JournalClient, JournalEntry

_LINE_LIMIT_BYTES = 1_048_576


class JournalFollower:
    """Streams a unit's journal lines as they are written."""

    def __init__(self, journal_client: JournalClient):
        """Creates the follower.

        Args:
            journal_client (JournalClient): Builds the journalctl arguments and parses its output.
        """
        self.journal_client = journal_client

    async def follow(
        self,
        unit_name: str,
        line_count: int,
    ) -> AsyncIterator[JournalEntry]:
        """Yields a unit's last lines and then every new line until the caller stops.

        The journalctl process is killed when the caller stops iterating.

        Args:
            unit_name (str): The unit to follow.
            line_count (int): How many earlier lines to yield first.

        Yields:
            JournalEntry: The next journal line.

        Raises:
            FileNotFoundError: journalctl is not installed.
        """
        process = await asyncio.create_subprocess_exec(
            *self.journal_client.follow_arguments(unit_name, line_count),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            limit=_LINE_LIMIT_BYTES,
        )
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                entry = self.journal_client.parse_line(line)
                if entry is not None:
                    yield entry
        finally:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()

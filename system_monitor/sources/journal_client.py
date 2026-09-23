"""Reads the systemd user journal through journalctl.

Typical usage example:

  client = JournalClient(CommandRunner())
  entries = client.read_after_cursor(None, since_epoch=time.time() - 900)
  cursor = entries[-1].cursor
"""

import dataclasses
import json

from system_monitor.sources.command_runner import CommandRunner

_OUTPUT_FIELDS = 'MESSAGE,_SYSTEMD_USER_UNIT,SYSLOG_IDENTIFIER'


class JournalError(Exception):
    """A journalctl command failed."""


@dataclasses.dataclass(frozen=True)
class JournalEntry:
    """One line of the journal.

    Attributes:
        unit: The user unit that wrote the line, such as "zerodha-instruments@websocket_quotes.service", or an empty string.
        identifier: The syslog identifier, such as "zerodha-quotes", or an empty string.
        timestamp: When the journal received the line, in epoch seconds.
        message: The line's text.
        cursor: The journal's position of this line, for reading on from it.
    """

    unit: str
    identifier: str
    timestamp: float
    message: str
    cursor: str


class JournalClient:
    """A thin wrapper over `journalctl --user` with JSON output."""

    def __init__(self, command_runner: CommandRunner):
        """Creates the client.

        Args:
            command_runner (CommandRunner): Runs the journalctl commands.
        """
        self.command_runner = command_runner

    def read_after_cursor(
        self,
        cursor: str | None,
        since_epoch: float,
    ) -> list[JournalEntry]:
        """Reads every user journal line after a cursor, or since a time when there is no cursor.

        Args:
            cursor (str | None): The cursor of the last line already read, or None.
            since_epoch (float): Where to start when there is no cursor, in epoch seconds.

        Returns:
            list[JournalEntry]: The lines, oldest first.

        Raises:
            JournalError: journalctl exited with an error.
        """
        arguments = self.base_arguments()
        if cursor:
            arguments.append('--after-cursor=' + cursor)
        else:
            arguments.append(f'--since=@{int(since_epoch)}')
        result = self.command_runner.run(arguments, timeout_seconds=30.0)
        if result.return_code != 0:
            raise JournalError(f'journalctl failed (exit {result.return_code}): {result.standard_error.strip()}')
        entries = []
        for line in result.standard_output.splitlines():
            entry = self.parse_line(line)
            if entry is not None:
                entries.append(entry)
        return entries

    def follow_arguments(self, unit_name: str, line_count: int) -> list[str]:
        """Builds the arguments that print a unit's last lines and then follow it.

        Args:
            unit_name (str): The unit to follow.
            line_count (int): How many earlier lines to print first.

        Returns:
            list[str]: The journalctl command and its arguments.
        """
        arguments = self.base_arguments()
        arguments.append('--unit=' + unit_name)
        arguments.append(f'--lines={line_count}')
        arguments.append('--follow')
        return arguments

    def base_arguments(self) -> list[str]:
        """Builds the arguments every journal read shares.

        Returns:
            list[str]: The journalctl command with JSON output options.
        """
        return [
            'journalctl',
            '--user',
            '--no-pager',
            '--output=json',
            '--output-fields=' + _OUTPUT_FIELDS,
        ]

    def parse_line(self, line: str | bytes) -> JournalEntry | None:
        """Parses one line of journalctl JSON output.

        Args:
            line (str | bytes): One JSON object as printed by journalctl.

        Returns:
            JournalEntry | None: The entry, or None when the line is blank or not a journal object.
        """
        if isinstance(line, bytes):
            line = line.decode('utf-8', errors='replace')
        line = line.strip()
        if not line:
            return None
        try:
            document = json.loads(line)
        except ValueError:
            return None
        if not isinstance(document, dict) or '__CURSOR' not in document:
            return None
        return JournalEntry(
            unit=self._text(document.get('_SYSTEMD_USER_UNIT')),
            identifier=self._text(document.get('SYSLOG_IDENTIFIER')),
            timestamp=int(document.get('__REALTIME_TIMESTAMP', '0')) / 1_000_000,
            message=self._text(document.get('MESSAGE')),
            cursor=document['__CURSOR'],
        )

    def _text(self, value: object) -> str:
        """Turns a journal field value into text.

        journalctl prints a field that is not valid UTF-8 as a list of byte values, and a missing field as null.

        Args:
            value (object): The field value from the JSON object.

        Returns:
            str: The field as text, or an empty string when it is missing.
        """
        if value is None:
            return ''
        if isinstance(value, list):
            byte_values = bytearray()
            for item in value:
                if isinstance(item, int):
                    byte_values.append(item)
            return byte_values.decode('utf-8', errors='replace')
        return str(value)

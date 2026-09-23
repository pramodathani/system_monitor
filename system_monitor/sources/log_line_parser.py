"""Finds the log level of a UBI journal line from its text.

UBI logs through `logging.basicConfig` to standard output with the format "%(asctime)s %(levelname)-8s %(name)s %(message)s", so the journal stores every line at priority 6 and the level exists only in the text. A line without that prefix, such as a traceback line, belongs to the log record before it and takes its level.

Typical usage example:

  parser = LogLineParser()
  parsed = parser.parse('zerodha-instruments@websocket_quotes.service', message)
  if parsed.level == 'ERROR':
      ...
"""

import dataclasses
import re

LEVELS = (
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL',
)

_PREFIX_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+(\S+)\s?(.*)$'
)
_TRACEBACK_START = 'Traceback (most recent call last)'


@dataclasses.dataclass(frozen=True)
class ParsedLogLine:
    """A journal line with its level worked out.

    Attributes:
        level: One of DEBUG, INFO, WARNING, ERROR or CRITICAL.
        logger_name: The Python logger that wrote the record, or None for a continuation line.
        text: The whole line as written.
        is_continuation: True when the line had no log prefix and took the previous record's level. A traceback's first line starts a record of its own.
    """

    level: str
    logger_name: str | None
    text: str
    is_continuation: bool


class LogLineParser:
    """Parses journal lines, remembering the last level seen for each unit."""

    def __init__(self):
        """Creates a parser with no remembered levels."""
        self._last_level_by_unit = {}

    def parse(self, unit_name: str, message: str) -> ParsedLogLine:
        """Works out the level of one line.

        Args:
            unit_name (str): The unit that wrote the line, used to remember its last level.
            message (str): The line's text.

        Returns:
            ParsedLogLine: The line with its level.
        """
        match = _PREFIX_PATTERN.match(message)
        if match is not None:
            level = match.group(1)
            self._last_level_by_unit[unit_name] = level
            return ParsedLogLine(
                level=level,
                logger_name=match.group(2),
                text=message,
                is_continuation=False,
            )
        if message.startswith(_TRACEBACK_START):
            self._last_level_by_unit[unit_name] = 'ERROR'
            return ParsedLogLine(
                level='ERROR',
                logger_name=None,
                text=message,
                is_continuation=False,
            )
        level = self._last_level_by_unit.get(unit_name, 'INFO')
        return ParsedLogLine(
            level=level,
            logger_name=None,
            text=message,
            is_continuation=True,
        )

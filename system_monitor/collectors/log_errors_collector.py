"""Counts warnings and errors each UBI unit logged recently.

The journal is read incrementally from the last cursor, and each line's level is parsed from its text. Only the first line of a record is counted, so a twenty-line traceback is one error.

Typical usage example:

  collector = LogErrorsCollector(journal_client, inventory, thresholds.logs, clock)
  outcome = collector.run_once()
"""

import collections
import dataclasses

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import LogThresholds
from system_monitor.sources.journal_client import JournalClient
from system_monitor.sources.log_line_parser import LogLineParser
from system_monitor.sources.unit_inventory import UnitInventory, UnitKind
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter

_COUNTED_LEVELS = (
    'WARNING',
    'ERROR',
    'CRITICAL',
)
_ERROR_LEVELS = (
    'ERROR',
    'CRITICAL',
)
_MAXIMUM_EVENTS = 20000
_MESSAGE_LIMIT = 400


@dataclasses.dataclass(frozen=True)
class _LogEvent:
    """One counted warning or error record.

    Attributes:
        timestamp: When it was logged, in epoch seconds.
        unit: The unit that logged it.
        level: WARNING, ERROR or CRITICAL.
        message: The record's first line.
    """

    timestamp: float
    unit: str
    level: str
    message: str


class LogErrorsCollector(BaseCollector):
    """Judges each unit by the warnings and errors in its recent journal."""

    name = 'logs'
    area = CheckArea.LOGS

    def __init__(
        self,
        journal_client: JournalClient,
        inventory: UnitInventory,
        thresholds: LogThresholds,
        clock: SystemClock,
        interval_seconds: float = 30.0,
    ):
        """Creates the collector.

        Args:
            journal_client (JournalClient): Reads the journal.
            inventory (UnitInventory): Says which units belong to UBI.
            thresholds (LogThresholds): The counting window.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.journal_client = journal_client
        self.inventory = inventory
        self.thresholds = thresholds
        self.parser = LogLineParser()
        self._cursor = None
        self._events = collections.deque(maxlen=_MAXIMUM_EVENTS)

    def collect(self) -> list[CheckResult]:
        """Reads new journal lines and judges every unit.

        Returns:
            list[CheckResult]: One result per non-timer UBI unit.

        Raises:
            JournalError: journalctl failed.
        """
        now = self.clock.now()
        window_start = now - self.thresholds.window_seconds
        entries = self.journal_client.read_after_cursor(self._cursor, window_start)
        for entry in entries:
            self._cursor = entry.cursor
            if not self.inventory.has_unit(entry.unit):
                continue
            parsed = self.parser.parse(entry.unit, entry.message)
            if parsed.is_continuation or parsed.level not in _COUNTED_LEVELS:
                continue
            self._events.append(
                _LogEvent(
                    timestamp=entry.timestamp,
                    unit=entry.unit,
                    level=parsed.level,
                    message=entry.message[:_MESSAGE_LIMIT],
                ),
            )
        while self._events and self._events[0].timestamp < window_start:
            self._events.popleft()

        warnings_by_unit = {}
        errors_by_unit = {}
        last_error_by_unit = {}
        last_warning_by_unit = {}
        for event in self._events:
            if event.level in _ERROR_LEVELS:
                errors_by_unit[event.unit] = errors_by_unit.get(event.unit, 0) + 1
                last_error_by_unit[event.unit] = event
            else:
                warnings_by_unit[event.unit] = warnings_by_unit.get(event.unit, 0) + 1
                last_warning_by_unit[event.unit] = event

        window_text = TextFormatter.duration(self.thresholds.window_seconds)
        results = []
        for unit in self.inventory.units():
            if unit.kind == UnitKind.TIMER:
                continue
            errors = errors_by_unit.get(unit.name, 0)
            warnings = warnings_by_unit.get(unit.name, 0)
            details = {
                'unit': unit.name,
                'errors': errors,
                'warnings': warnings,
                'window_seconds': self.thresholds.window_seconds,
                'last_error': self._event_details(last_error_by_unit.get(unit.name)),
                'last_warning': self._event_details(last_warning_by_unit.get(unit.name)),
            }
            if errors > 0:
                status = CheckStatus.WARNING
                message = f'{errors} errors and {warnings} warnings in the last {window_text}.'
            elif warnings > 0:
                status = CheckStatus.OK
                message = f'{warnings} warnings in the last {window_text}.'
            else:
                status = CheckStatus.OK
                message = f'No warnings or errors in the last {window_text}.'
            results.append(
                self.result(
                    unit.name,
                    unit.subject,
                    unit.name.removesuffix('.service'),
                    status,
                    message,
                    value=float(errors),
                    details=details,
                ),
            )
        return results

    def _event_details(self, event: _LogEvent | None) -> dict[str, object] | None:
        """Converts a remembered event for the dashboard.

        Args:
            event (_LogEvent | None): The event, or None.

        Returns:
            dict[str, object] | None: The event's time and message, or None.
        """
        if event is None:
            return None
        return {
            'at': event.timestamp,
            'message': event.message,
        }

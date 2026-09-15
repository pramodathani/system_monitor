"""Tests for LogErrorsCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.log_errors_collector import LogErrorsCollector
from system_monitor.configuration.thresholds import LogThresholds
from system_monitor.sources.journal_client import JournalEntry
from tests.fakes import FakeUnitInventory, FixedClock


class _FakeJournalClient:
    """A journal client that returns queued batches of entries."""

    def __init__(self):
        """Creates a client with no batches."""
        self.batches = []
        self.calls = []

    def read_after_cursor(self, cursor: str | None, since_epoch: float) -> list[JournalEntry]:
        """Returns the next queued batch.

        Args:
            cursor (str | None): The cursor passed by the collector.
            since_epoch (float): The start time passed by the collector.

        Returns:
            list[JournalEntry]: The next batch, or an empty list.
        """
        self.calls.append((cursor, since_epoch))
        if not self.batches:
            return []
        return self.batches.pop(0)


class TestLogErrorsCollector:
    """Tests for LogErrorsCollector."""

    def _entry(self, unit: str, timestamp: float, message: str, cursor: str) -> JournalEntry:
        """Builds a journal entry.

        Args:
            unit (str): The unit.
            timestamp (float): The entry time.
            message (str): The text.
            cursor (str): The cursor.

        Returns:
            JournalEntry: The entry.
        """
        return JournalEntry(
            unit=unit,
            identifier='',
            timestamp=timestamp,
            message=message,
            cursor=cursor,
        )

    def test_collect_counts_records_and_expires_them(self):
        """Checks record counting, traceback handling, foreign units, cursors and the window.

        Raises:
            AssertionError: A count, status or cursor is wrong.
        """
        inventory = FakeUnitInventory(
            {
                'kotak': [
                    'kotak@positions.service',
                    'kotak@trades.service',
                    'kotak-login.timer',
                    'kotak-login.service',
                ],
            },
        )
        clock = FixedClock(10_000.0)
        journal = _FakeJournalClient()
        unit = 'kotak@positions.service'
        journal.batches.append(
            [
                self._entry(unit, 9_990, '2026-09-15 12:00:00 ERROR    kotak.positions Poll failed', 'c1'),
                self._entry(unit, 9_990, 'Traceback (most recent call last):', 'c2'),
                self._entry(unit, 9_990, '  File "bin/kotak/positions", line 1', 'c3'),
                self._entry(unit, 9_991, '2026-09-15 12:00:01 WARNING  kotak.positions Retrying', 'c4'),
                self._entry('gnome-shell.service', 9_992, '2026-09-15 12:00:02 ERROR    shell boom', 'c5'),
            ],
        )
        collector = LogErrorsCollector(journal, inventory, LogThresholds(window_seconds=900), clock)
        results = {}
        for result in collector.collect():
            results[result.check_id] = result
        assert set(results) == {
            'logs:kotak@positions.service',
            'logs:kotak@trades.service',
            'logs:kotak-login.service',
        }
        positions = results['logs:kotak@positions.service']
        assert positions.status == CheckStatus.WARNING
        assert positions.details['errors'] == 2
        assert positions.details['warnings'] == 1
        assert positions.details['last_warning']['message'].endswith('Retrying')
        assert results['logs:kotak@trades.service'].status == CheckStatus.OK
        assert journal.calls[0] == (None, 9_100.0)

        clock.advance(1000)
        results = {}
        for result in collector.collect():
            results[result.check_id] = result
        assert journal.calls[1][0] == 'c5'
        assert results['logs:kotak@positions.service'].status == CheckStatus.OK
        assert results['logs:kotak@positions.service'].details['errors'] == 0

"""Tests for ReferenceDataCollector."""

import datetime

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.reference_data_collector import ReferenceDataCollector
from system_monitor.configuration.thresholds import ReferenceDataThresholds
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock


class TestReferenceDataCollector:
    """Tests for ReferenceDataCollector."""

    def _collect(self, reader: FakeRedisReader, clock: FixedClock) -> dict:
        """Runs the collector for zerodha and unified.

        Args:
            reader (FakeRedisReader): The prepared Redis contents.
            clock (FixedClock): The test clock.

        Returns:
            dict: The results keyed by check_id.
        """
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha-instruments@websocket_quotes.service',
                ],
                'unified': [
                    'unified-instruments@websocket_quotes.service',
                ],
            },
        )
        collector = ReferenceDataCollector(
            reader,
            inventory,
            ReferenceDataThresholds(expected_by=datetime.time(9, 0)),
            clock,
        )
        indexed = {}
        for result in collector.collect():
            indexed[result.check_id] = result
        return indexed

    def _reader(self, download_date: str) -> FakeRedisReader:
        """Prepares instrument and mapping meta documents for a date.

        Args:
            download_date (str): The date both documents were produced for.

        Returns:
            FakeRedisReader: The prepared fake Redis.
        """
        reader = FakeRedisReader()
        reader.set_json(
            'zerodha:instruments:meta',
            {
                'download_date': download_date,
                'rows': 110315,
                'written_at': f'{download_date} 07:45:56',
            },
        )
        reader.set_json(
            'unified:mapping:meta',
            {
                'mapping_date': download_date,
                'instruments': 527779,
                'written_at': f'{download_date} 08:01:51',
            },
        )
        return reader

    def test_collect_today_is_ok(self):
        """Checks that today's download and mapping are ok.

        Raises:
            AssertionError: A status or message is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        results = self._collect(self._reader('2026-09-15'), clock)
        assert results['reference_data:zerodha:instruments'].status == CheckStatus.OK
        assert results['reference_data:zerodha:instruments'].message == 'Done for today, 110,315 instruments.'
        assert results['reference_data:unified:mapping'].status == CheckStatus.OK

    def test_collect_yesterday_fails_after_expected_time(self):
        """Checks that yesterday's data fails at 11:00 but not at 08:00.

        Raises:
            AssertionError: A status is wrong.
        """
        reader = self._reader('2026-09-14')
        late = self._collect(reader, FixedClock.at_india_time(2026, 9, 15, 11, 0))
        early = self._collect(reader, FixedClock.at_india_time(2026, 9, 15, 8, 0))
        assert late['reference_data:zerodha:instruments'].status == CheckStatus.FAILURE
        assert early['reference_data:zerodha:instruments'].status == CheckStatus.OK

    def test_collect_weekend_stale_data_fails(self):
        """Checks that Friday's data fails on a Sunday, because UBI maps every day.

        Raises:
            AssertionError: The status is wrong.
        """
        results = self._collect(self._reader('2026-09-11'), FixedClock.at_india_time(2026, 9, 13, 11, 0))
        assert results['reference_data:unified:mapping'].status == CheckStatus.FAILURE

    def test_collect_weekend_today_is_ok(self):
        """Checks that Sunday's own download and mapping are ok on that Sunday.

        Raises:
            AssertionError: The status is wrong.
        """
        results = self._collect(self._reader('2026-09-13'), FixedClock.at_india_time(2026, 9, 13, 11, 0))
        assert results['reference_data:zerodha:instruments'].status == CheckStatus.OK
        assert results['reference_data:unified:mapping'].status == CheckStatus.OK

    def test_collect_prices_failed_step_warns(self):
        """Checks the real shape of a prices run whose verify step failed.

        Raises:
            AssertionError: The status or message is wrong.
        """
        reader = self._reader('2026-09-15')
        reader.set_json(
            'unified:prices:last_run',
            {
                'step': 'daily',
                'steps': [
                    {
                        'step': 'load',
                        'exit_code': 0,
                    },
                    {
                        'step': 'verify',
                        'exit_code': 1,
                    },
                ],
                'started': '2026-09-15 08:30:12',
                'finished': '2026-09-15 09:36:45',
                'exit_code': 0,
            },
        )
        result = self._collect(reader, FixedClock.at_india_time(2026, 9, 15, 11, 0))['reference_data:unified:prices']
        assert result.status == CheckStatus.WARNING
        assert result.message == 'The last run finished 2026-09-15 09:36:45 with failed steps: verify (exit 1).'

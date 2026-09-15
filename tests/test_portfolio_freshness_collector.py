"""Tests for PortfolioFreshnessCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.portfolio_freshness_collector import (
    PortfolioFreshnessCollector,
)
from system_monitor.configuration.thresholds import PortfolioThresholds
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock

_THRESHOLDS = PortfolioThresholds(
    warning_age_seconds=60,
    failure_age_seconds=300,
    holdings_warning_age_seconds=180,
    holdings_failure_age_seconds=600,
)


class TestPortfolioFreshnessCollector:
    """Tests for PortfolioFreshnessCollector."""

    def _collect(self, reader: FakeRedisReader, clock: FixedClock) -> dict:
        """Runs the collector for kotak (orders, funds, holdings) and unified (positions).

        Args:
            reader (FakeRedisReader): The prepared Redis contents.
            clock (FixedClock): The test clock.

        Returns:
            dict: The results keyed by check_id.
        """
        inventory = FakeUnitInventory(
            {
                'kotak': [
                    'kotak@orders.service',
                    'kotak@funds.service',
                    'kotak@holdings.service',
                ],
                'unified': [
                    'unified@positions.service',
                ],
            },
        )
        indexed = {}
        for result in PortfolioFreshnessCollector(reader, inventory, _THRESHOLDS, clock).collect():
            indexed[result.check_id] = result
        return indexed

    def test_collect_only_datasets_with_services(self):
        """Checks that positions and trades are not checked for kotak here.

        Raises:
            AssertionError: The checks are wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        results = self._collect(FakeRedisReader(), clock)
        assert set(results) == {
            'portfolio:kotak:orders',
            'portfolio:kotak:funds',
            'portfolio:kotak:holdings',
            'portfolio:unified:positions',
        }
        assert results['portfolio:kotak:orders'].status == CheckStatus.FAILURE

    def test_collect_ages_and_poll_status(self):
        """Checks an old polled_at, a fresh but unsuccessful funds poll, and holdings' longer limit.

        Raises:
            AssertionError: A status is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        reader = FakeRedisReader()
        reader.strings['kotak:orders:orders:polled_at'] = str(clock.now() - 3 * 3600)
        reader.set_json(
            'kotak:portfolio:funds',
            {
                'timestamp': '2026-09-15 10:59:58',
                'status': 'failure',
                'code': 500,
                'data': None,
            },
        )
        reader.set_json(
            'kotak:portfolio:holdings',
            {
                'timestamp': '2026-09-15 10:57:00',
                'status': 'success',
                'code': 200,
                'data': [],
            },
        )
        results = self._collect(reader, clock)
        assert results['portfolio:kotak:orders'].status == CheckStatus.FAILURE
        assert results['portfolio:kotak:orders'].message == 'Not read for 3 h 0 min.'
        assert results['portfolio:kotak:funds'].status == CheckStatus.WARNING
        assert results['portfolio:kotak:holdings'].status == CheckStatus.OK

    def test_collect_unified_names_stale_brokers(self):
        """Checks that a fresh combined document with a stale broker is a warning naming it.

        Raises:
            AssertionError: The status or message is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        reader = FakeRedisReader()
        reader.set_json(
            'unified:portfolio:positions',
            {
                'net': [],
                'summary': {},
                'brokers': [
                    {
                        'broker': 'dhan',
                        'status': 'ok',
                        'as_of': '2026-09-15T10:59:59',
                    },
                    {
                        'broker': 'kotak',
                        'status': 'stale',
                        'as_of': '2026-09-15T07:46:00',
                    },
                ],
                'as_of': '2026-09-15T10:59:59',
            },
        )
        result = self._collect(reader, clock)['portfolio:unified:positions']
        assert result.status == CheckStatus.WARNING
        assert result.message == 'Combined without fresh data from: kotak stale.'

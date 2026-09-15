"""Tests for QuotesPipelineCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.quotes_pipeline_collector import QuotesPipelineCollector
from system_monitor.configuration.thresholds import QuotesPipelineThresholds
from system_monitor.sources.market_calendar import MarketCalendar
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock


class TestQuotesPipelineCollector:
    """Tests for QuotesPipelineCollector."""

    def _setup(self, clock: FixedClock) -> tuple[QuotesPipelineCollector, FakeRedisReader]:
        """Builds a collector with a unified quotes service.

        Args:
            clock (FixedClock): The test clock.

        Returns:
            tuple[QuotesPipelineCollector, FakeRedisReader]: A tuple (collector, reader).
        """
        inventory = FakeUnitInventory(
            {
                'unified': [
                    'unified@quotes.service',
                ],
            },
        )
        reader = FakeRedisReader()
        collector = QuotesPipelineCollector(
            reader,
            inventory,
            MarketCalendar(None, clock),
            QuotesPipelineThresholds(
                stats_failure_age_seconds=30,
                stale_scan_interval_seconds=30,
            ),
            clock,
        )
        return collector, reader

    def _stats(self, reader: FakeRedisReader, at: float, received: int, written: int, undecodable: int = 0) -> None:
        """Stores a statistics document.

        Args:
            reader (FakeRedisReader): The fake Redis.
            at (float): The document's write time.
            received (int): The received counter.
            written (int): The written counter.
            undecodable (int): The undecodable counter.
        """
        reader.set_json(
            'unified:quotes:stats',
            {
                'at': at,
                'pipeline': {
                    'received': received,
                    'written': written,
                },
                'undecodable': undecodable,
                'plans': 101,
                'mapping_date': '2026-09-15',
            },
        )

    def _by_id(self, collector: QuotesPipelineCollector) -> dict:
        """Runs the collector and indexes the results.

        Args:
            collector (QuotesPipelineCollector): The collector.

        Returns:
            dict: The results keyed by check_id.
        """
        indexed = {}
        for result in collector.collect():
            indexed[result.check_id] = result
        return indexed

    def test_collect_rates_from_document_times(self):
        """Checks that rates use the documents' own times.

        Raises:
            AssertionError: The rate or message is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stats(reader, clock.now() - 12, 1000, 100)
        self._by_id(collector)
        clock.advance(10)
        self._stats(reader, clock.now() - 12, 2000, 200)
        result = self._by_id(collector)['quotes_pipeline:stats']
        assert result.status == CheckStatus.OK
        assert result.value == 10.0
        assert result.message == '10.0 quotes/s written from 100.0 ticks/s received.'

    def test_collect_old_stats_fail(self):
        """Checks that a stale heartbeat is a failure.

        Raises:
            AssertionError: The result is not a failure.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stats(reader, clock.now() - 120, 1000, 100)
        assert self._by_id(collector)['quotes_pipeline:stats'].status == CheckStatus.FAILURE

    def test_collect_undecodable_growth_warns(self):
        """Checks that newly undecodable ticks produce a warning.

        Raises:
            AssertionError: The result is not a warning.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stats(reader, clock.now(), 1000, 100, undecodable=0)
        self._by_id(collector)
        clock.advance(10)
        self._stats(reader, clock.now(), 1100, 110, undecodable=3)
        assert self._by_id(collector)['quotes_pipeline:stats'].status == CheckStatus.WARNING

    def test_collect_stale_quotes_only_warn_while_market_open(self):
        """Checks that a stale NSE quote warns at 11:00 but not at 19:00, while MCX is still open.

        Raises:
            AssertionError: A status is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stats(reader, clock.now(), 1, 1)
        reader.set_hash_json(
            'unified:quotes:live',
            'a',
            {
                'broker': 'groww',
                'exchange': 'nse',
                'stale': True,
            },
        )
        reader.set_hash_json(
            'unified:quotes:live',
            'b',
            {
                'broker': 'zerodha',
                'exchange': 'mcx',
                'stale': False,
            },
        )
        morning = self._by_id(collector)['quotes_pipeline:stale_quotes']
        assert morning.status == CheckStatus.WARNING
        assert morning.message == '1 of 2 live quotes are stale while their market is open.'

        clock.advance(8 * 3600)
        self._stats(reader, clock.now(), 2, 2)
        evening = self._by_id(collector)['quotes_pipeline:stale_quotes']
        assert evening.status == CheckStatus.OK
        assert evening.details['stale_while_closed'] == 1

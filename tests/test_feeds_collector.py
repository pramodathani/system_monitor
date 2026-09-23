"""Tests for FeedsCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.feeds_collector import FeedsCollector
from system_monitor.configuration.thresholds import FeedAgeLimits, FeedThresholds
from system_monitor.sources.market_calendar import MarketCalendar
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock

_THRESHOLDS = FeedThresholds(
    default_limits=FeedAgeLimits(
        warning_age_seconds=45,
        failure_age_seconds=120,
    ),
    grace_after_open_seconds=300,
    broker_overrides={},
)


class TestFeedsCollector:
    """Tests for FeedsCollector."""

    def _setup(self, clock: FixedClock) -> tuple[FeedsCollector, FakeRedisReader]:
        """Builds a collector for zerodha (NSE and MCX) and groww (NSE only), using the built-in calendar.

        Args:
            clock (FixedClock): The test clock.

        Returns:
            tuple[FeedsCollector, FakeRedisReader]: A tuple (collector, reader).
        """
        inventory = FakeUnitInventory(
            {
                'groww': [
                    'groww-instruments@websocket_quotes.service',
                ],
                'zerodha': [
                    'zerodha-instruments@websocket_quotes.service',
                ],
                'kotak': [
                    'kotak-orders@api_order_details.service',
                ],
            },
        )
        reader = FakeRedisReader()
        reader.set_hash_json(
            'zerodha:quotes:live',
            'MCX:GOLDM',
            {
                'exchange': 'mcx',
            },
        )
        reader.set_hash_json(
            'zerodha:quotes:live',
            'NSE:INFY',
            {
                'exchange': 'nse',
            },
        )
        reader.set_hash_json(
            'groww:quotes:live',
            'NSE:HDFCBANK',
            {
                'exchange': 'NSE',
            },
        )
        calendar = MarketCalendar(None, clock)
        collector = FeedsCollector(reader, inventory, calendar, _THRESHOLDS, clock)
        return collector, reader

    def _stream(self, reader: FakeRedisReader, subject: str, last_tick_epoch: float, entries_added: int) -> None:
        """Prepares a quote stream whose newest entry is at a given time.

        Args:
            reader (FakeRedisReader): The fake Redis.
            subject (str): The broker name.
            last_tick_epoch (float): The newest entry's time.
            entries_added (int): The stream's entries-added counter.
        """
        reader.streams[f'{subject}:quotes:stream'] = {
            'length': 100,
            'last-generated-id': f'{int(last_tick_epoch * 1000)}-0',
            'entries-added': entries_added,
        }

    def _by_id(self, collector: FeedsCollector) -> dict:
        """Runs the collector and indexes the results.

        Args:
            collector (FeedsCollector): The collector.

        Returns:
            dict: The results keyed by check_id.
        """
        indexed = {}
        for result in collector.collect():
            indexed[result.check_id] = result
        return indexed

    def test_collect_only_subjects_with_quotes_service(self):
        """Checks that kotak, which runs no quotes service here, gets no feed check.

        Raises:
            AssertionError: The subjects are wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now(), 10)
        self._stream(reader, 'groww', clock.now(), 10)
        assert set(self._by_id(collector)) == {
            'feeds:groww',
            'feeds:zerodha',
        }

    def test_collect_rate_and_ok_during_session(self):
        """Checks a fresh feed and its rate on the second run.

        Raises:
            AssertionError: The status or rate is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now(), 1000)
        self._stream(reader, 'groww', clock.now(), 10)
        first = self._by_id(collector)['feeds:zerodha']
        assert first.status == CheckStatus.OK
        assert first.value is None
        clock.advance(5)
        self._stream(reader, 'zerodha', clock.now(), 1050)
        second = self._by_id(collector)['feeds:zerodha']
        assert second.value == 10.0
        assert second.message == '10.0 ticks/s; last tick 0 s ago.'

    def test_collect_silent_feed_fails_while_open(self):
        """Checks a feed silent for five minutes in the middle of the session.

        Raises:
            AssertionError: The status is not a failure.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 11, 0)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now() - 300, 10)
        self._stream(reader, 'groww', clock.now() - 60, 10)
        results = self._by_id(collector)
        assert results['feeds:zerodha'].status == CheckStatus.FAILURE
        assert results['feeds:groww'].status == CheckStatus.WARNING

    def test_collect_nse_only_feed_idle_in_evening(self):
        """Checks that at 19:00 the NSE-only feed is idle while the MCX feed is still judged.

        Raises:
            AssertionError: A status is wrong.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 19, 0)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now() - 300, 10)
        self._stream(reader, 'groww', clock.now() - 3 * 3600, 10)
        results = self._by_id(collector)
        assert results['feeds:groww'].status == CheckStatus.IDLE
        assert results['feeds:zerodha'].status == CheckStatus.FAILURE

    def test_collect_grace_after_open(self):
        """Checks that a silent NSE-only feed two minutes after 09:15 is idle, not failed.

        Raises:
            AssertionError: The status is not idle.
        """
        clock = FixedClock.at_india_time(2026, 9, 15, 9, 17)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now(), 10)
        self._stream(reader, 'groww', clock.now() - 18 * 3600, 10)
        assert self._by_id(collector)['feeds:groww'].status == CheckStatus.IDLE

    def test_collect_weekend_is_idle(self):
        """Checks that feeds are idle on a Sunday.

        Raises:
            AssertionError: The status is not idle.
        """
        clock = FixedClock.at_india_time(2026, 9, 13, 11, 0)
        collector, reader = self._setup(clock)
        self._stream(reader, 'zerodha', clock.now() - 86400, 10)
        self._stream(reader, 'groww', clock.now() - 86400, 10)
        results = self._by_id(collector)
        assert results['feeds:zerodha'].status == CheckStatus.IDLE
        assert results['feeds:groww'].status == CheckStatus.IDLE

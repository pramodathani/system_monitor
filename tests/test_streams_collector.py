"""Tests for StreamsCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.streams_collector import StreamsCollector
from system_monitor.configuration.thresholds import StreamThresholds
from tests.fakes import FakeRedisReader, FakeUnitInventory, FixedClock

_THRESHOLDS = StreamThresholds(
    warning_lag_fraction=0.05,
    failure_lag_fraction=0.5,
    pending_warning=1000,
    caps={
        'broker_quotes': 100000,
        'broker_order_updates': 20000,
        'broker_positions_updates': 20000,
        'unified_quotes': 200000,
        'unified_order_updates': 50000,
        'unified_positions_updates': 50000,
    },
)


class TestStreamsCollector:
    """Tests for StreamsCollector."""

    def _collect(self, reader: FakeRedisReader) -> dict:
        """Runs the collector for zerodha and unified.

        Args:
            reader (FakeRedisReader): The prepared Redis contents.

        Returns:
            dict: The results keyed by check_id.
        """
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha@quotes.service',
                ],
                'unified': [
                    'unified@quotes.service',
                ],
            },
        )
        indexed = {}
        for result in StreamsCollector(reader, inventory, _THRESHOLDS, FixedClock(0)).collect():
            indexed[result.check_id] = result
        return indexed

    def _group(self, name: str, lag: int | None, pending: int = 0, consumers: int = 1) -> dict:
        """Builds one XINFO GROUPS entry.

        Args:
            name (str): The group name.
            lag (int | None): The group's lag.
            pending (int): The pending count.
            consumers (int): The consumer count.

        Returns:
            dict: The entry.
        """
        return {
            'name': name,
            'lag': lag,
            'pending': pending,
            'consumers': consumers,
            'last-delivered-id': '1-0',
        }

    def test_collect_judges_each_group(self):
        """Checks ok, warning and failure groups, and that missing streams are skipped.

        Raises:
            AssertionError: A status is wrong.
        """
        reader = FakeRedisReader()
        reader.streams['zerodha:quotes:stream'] = {
            'length': 100000,
            'last-generated-id': '2-0',
        }
        reader.groups['zerodha:quotes:stream'] = [
            self._group('persist', 60000),
            self._group('unified', 0, pending=4),
        ]
        reader.streams['zerodha:order-updates:stream'] = {
            'length': 10,
            'last-generated-id': '2-0',
        }
        reader.groups['zerodha:order-updates:stream'] = [
            self._group('persist', 1500),
            self._group('unified', 0, pending=2000),
        ]
        results = self._collect(reader)
        assert results['streams:zerodha:quotes:stream:persist'].status == CheckStatus.FAILURE
        assert results['streams:zerodha:quotes:stream:unified'].status == CheckStatus.OK
        assert results['streams:zerodha:order-updates:stream:persist'].status == CheckStatus.WARNING
        assert results['streams:zerodha:order-updates:stream:unified'].status == CheckStatus.WARNING
        assert 'streams:zerodha:positions_updates:stream' not in str(results)

    def test_collect_unified_cap_and_missing_groups(self):
        """Checks that unified streams use their larger cap and that a stream without groups warns.

        Raises:
            AssertionError: A status is wrong.
        """
        reader = FakeRedisReader()
        reader.streams['unified:quotes:stream'] = {
            'length': 200000,
            'last-generated-id': '2-0',
        }
        reader.groups['unified:quotes:stream'] = [
            self._group('persist', 60000),
        ]
        reader.streams['unified:order-updates:stream'] = {
            'length': 5,
            'last-generated-id': '2-0',
        }
        results = self._collect(reader)
        assert results['streams:unified:quotes:stream:persist'].status == CheckStatus.WARNING
        assert results['streams:unified:quotes:stream:persist'].details['cap'] == 200000
        assert results['streams:unified:order-updates:stream'].status == CheckStatus.WARNING

    def test_collect_unknown_lag_and_no_consumer_warn(self):
        """Checks a group whose lag is unknown and one with nobody reading.

        Raises:
            AssertionError: A status is wrong.
        """
        reader = FakeRedisReader()
        reader.streams['zerodha:quotes:stream'] = {
            'length': 100,
            'last-generated-id': '2-0',
        }
        reader.groups['zerodha:quotes:stream'] = [
            self._group('persist', None),
            self._group('unified', 10, consumers=0),
        ]
        results = self._collect(reader)
        assert results['streams:zerodha:quotes:stream:persist'].status == CheckStatus.WARNING
        assert results['streams:zerodha:quotes:stream:unified'].status == CheckStatus.WARNING

"""Tests for ServicesCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.services_collector import ServicesCollector
from system_monitor.configuration.thresholds import ServiceThresholds
from tests.fakes import FakeSystemdClient, FakeUnitInventory, FixedClock


class TestServicesCollector:
    """Tests for ServicesCollector."""

    def _collector(self) -> tuple[ServicesCollector, FakeSystemdClient, FixedClock]:
        """Builds a collector over zerodha's quotes, orders and historical prices units.

        Returns:
            tuple[ServicesCollector, FakeSystemdClient, FixedClock]: A tuple (collector, systemd client, clock).
        """
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha-instruments@websocket_quotes.service',
                    'zerodha-orders@api_order_details.service',
                    'zerodha-historical-prices.service',
                    'zerodha-login.service',
                    'zerodha-login.timer',
                ],
            },
        )
        systemd_client = FakeSystemdClient()
        clock = FixedClock(1_000_000.0)
        collector = ServicesCollector(
            systemd_client,
            inventory,
            ServiceThresholds(restart_window_seconds=900),
            clock,
        )
        return collector, systemd_client, clock

    def _running(self, restarts: int = 0) -> dict[str, str]:
        """Builds the properties of a running unit started an hour before the test clock.

        Args:
            restarts (int): The NRestarts value.

        Returns:
            dict[str, str]: The properties.
        """
        return {
            'LoadState': 'loaded',
            'ActiveState': 'active',
            'SubState': 'running',
            'Result': 'success',
            'NRestarts': str(restarts),
            'ExecMainStartTimestamp': '@996400',
        }

    def _by_id(self, results: list) -> dict:
        """Indexes results by check id.

        Args:
            results (list): The results.

        Returns:
            dict: The results keyed by check_id.
        """
        indexed = {}
        for result in results:
            indexed[result.check_id] = result
        return indexed

    def test_collect_skips_timers_and_scheduled_units(self):
        """Checks that only long-running and periodic units are judged here.

        Raises:
            AssertionError: A timer or scheduled unit was judged.
        """
        collector, systemd_client, _clock = self._collector()
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = self._running()
        results = self._by_id(collector.collect())
        assert set(results) == {
            'services:zerodha-instruments@websocket_quotes.service',
            'services:zerodha-orders@api_order_details.service',
            'services:zerodha-historical-prices.service',
        }

    def test_collect_running_is_ok_with_uptime(self):
        """Checks a healthy unit.

        Raises:
            AssertionError: The result is wrong.
        """
        collector, systemd_client, _clock = self._collector()
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = self._running()
        result = self._by_id(collector.collect())['services:zerodha-instruments@websocket_quotes.service']
        assert result.status == CheckStatus.OK
        assert result.value == 3600
        assert result.message == 'Running for 1 h 0 min.'

    def test_collect_missing_unit_is_failure(self):
        """Checks that a unit systemd does not report is a failure.

        Raises:
            AssertionError: The result is not a failure.
        """
        collector, _systemd_client, _clock = self._collector()
        result = self._by_id(collector.collect())['services:zerodha-orders@api_order_details.service']
        assert result.status == CheckStatus.FAILURE

    def test_collect_auto_restart_depends_on_kind(self):
        """Checks that waiting to restart is normal only for periodic units.

        Raises:
            AssertionError: A status is wrong.
        """
        collector, systemd_client, _clock = self._collector()
        waiting = {
            'LoadState': 'loaded',
            'ActiveState': 'activating',
            'SubState': 'auto-restart',
            'Result': 'exit-code',
            'NRestarts': '1',
            'ExecMainStartTimestamp': '',
        }
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = waiting
        systemd_client.properties['zerodha-historical-prices.service'] = waiting
        results = self._by_id(collector.collect())
        assert results['services:zerodha-instruments@websocket_quotes.service'].status == CheckStatus.WARNING
        assert results['services:zerodha-historical-prices.service'].status == CheckStatus.OK

    def test_collect_failed_unit_is_failure(self):
        """Checks a unit systemd gave up on.

        Raises:
            AssertionError: The result is not a failure.
        """
        collector, systemd_client, _clock = self._collector()
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = {
            'LoadState': 'loaded',
            'ActiveState': 'failed',
            'SubState': 'failed',
            'Result': 'exit-code',
        }
        result = self._by_id(collector.collect())['services:zerodha-instruments@websocket_quotes.service']
        assert result.status == CheckStatus.FAILURE
        assert 'exit-code' in result.message

    def test_collect_recent_restarts_warn_then_clear(self):
        """Checks that a restart-count rise warns inside the window and clears after it.

        Raises:
            AssertionError: The warning did not appear or did not clear.
        """
        collector, systemd_client, clock = self._collector()
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = self._running(restarts=2)
        assert self._by_id(collector.collect())['services:zerodha-instruments@websocket_quotes.service'].status == CheckStatus.OK

        clock.advance(60)
        systemd_client.properties['zerodha-instruments@websocket_quotes.service'] = self._running(restarts=3)
        result = self._by_id(collector.collect())['services:zerodha-instruments@websocket_quotes.service']
        assert result.status == CheckStatus.WARNING
        assert result.details['recent_restarts'] == 1

        clock.advance(1000)
        collector.collect()
        clock.advance(5)
        result = self._by_id(collector.collect())['services:zerodha-instruments@websocket_quotes.service']
        assert result.status == CheckStatus.OK

"""Tests for TimersCollector."""

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.timers_collector import TimersCollector
from tests.fakes import FakeSystemdClient, FakeUnitInventory, FixedClock


class TestTimersCollector:
    """Tests for TimersCollector."""

    def _collect(self, service_properties: dict[str, str], timer_properties: dict[str, str] | None = None):
        """Runs the collector over one login timer and its service.

        Args:
            service_properties (dict[str, str]): The login service's properties.
            timer_properties (dict[str, str] | None): The timer's properties, or None for an active timer triggered at 1000.

        Returns:
            CheckResult: The timer's result.
        """
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha-login.service',
                    'zerodha-login.timer',
                ],
            },
        )
        systemd_client = FakeSystemdClient()
        if timer_properties is None:
            timer_properties = {
                'ActiveState': 'active',
                'LastTriggerUSec': '@1000',
                'NextElapseUSecRealtime': '@90000',
            }
        systemd_client.properties['zerodha-login.timer'] = timer_properties
        systemd_client.properties['zerodha-login.service'] = service_properties
        collector = TimersCollector(systemd_client, inventory, FixedClock(2000.0))
        results = collector.collect()
        assert len(results) == 1
        return results[0]

    def test_collect_finished_after_trigger_is_ok(self):
        """Checks a job that finished successfully after its trigger.

        Raises:
            AssertionError: The result is wrong.
        """
        result = self._collect(
            {
                'LoadState': 'loaded',
                'ActiveState': 'inactive',
                'SubState': 'dead',
                'Result': 'success',
                'ExecMainExitTimestamp': '@1010',
            },
        )
        assert result.status == CheckStatus.OK
        assert result.check_id == 'timers:zerodha-login.timer'
        assert result.details['service'] == 'zerodha-login.service'

    def test_collect_failed_job_is_failure(self):
        """Checks a job whose last run failed.

        Raises:
            AssertionError: The result is not a failure.
        """
        result = self._collect(
            {
                'LoadState': 'loaded',
                'ActiveState': 'failed',
                'SubState': 'failed',
                'Result': 'exit-code',
                'ExecMainStatus': '1',
                'ExecMainExitTimestamp': '@1010',
            },
        )
        assert result.status == CheckStatus.FAILURE
        assert 'exit status 1' in result.message

    def test_collect_running_job_is_ok(self):
        """Checks a oneshot job that is running now.

        Raises:
            AssertionError: The result is wrong.
        """
        result = self._collect(
            {
                'LoadState': 'loaded',
                'ActiveState': 'activating',
                'SubState': 'start',
                'Result': 'success',
                'ExecMainStartTimestamp': '@1900',
            },
        )
        assert result.status == CheckStatus.OK
        assert result.message == 'Running now, started 1 min 40 s ago.'

    def test_collect_never_triggered_is_idle(self):
        """Checks a timer that has not fired since it was loaded.

        Raises:
            AssertionError: The result is not idle.
        """
        result = self._collect(
            {
                'LoadState': 'loaded',
                'ActiveState': 'inactive',
                'SubState': 'dead',
                'Result': 'success',
            },
            {
                'ActiveState': 'active',
                'LastTriggerUSec': '',
                'NextElapseUSecRealtime': '@90000',
            },
        )
        assert result.status == CheckStatus.IDLE

    def test_collect_inactive_timer_is_failure(self):
        """Checks a timer that is not active.

        Raises:
            AssertionError: The result is not a failure.
        """
        result = self._collect(
            {
                'LoadState': 'loaded',
                'ActiveState': 'inactive',
                'SubState': 'dead',
                'Result': 'success',
            },
            {
                'ActiveState': 'inactive',
            },
        )
        assert result.status == CheckStatus.FAILURE

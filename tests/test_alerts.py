"""Tests for AlertPolicy, DesktopNotifier and AlertDispatcher."""

import asyncio

from system_monitor.alerts.alert_dispatcher import AlertDispatcher
from system_monitor.alerts.alert_policy import AlertPolicy, Notification
from system_monitor.alerts.desktop_notifier import DesktopNotifier
from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.configuration.thresholds import AlertThresholds
from tests.fakes import FakeCommandRunner, FixedClock

_THRESHOLDS = AlertThresholds(
    consecutive_failures=2,
    cooldown_seconds=600,
    group_threshold=3,
)


class _Results:
    """Builds results for the alert tests."""

    @staticmethod
    def one(subject: str, status: CheckStatus) -> CheckResult:
        """Builds a feed result for a subject.

        Args:
            subject (str): The broker name.
            status (CheckStatus): The status.

        Returns:
            CheckResult: The result.
        """
        return CheckResult(
            check_id=f'feeds:{subject}',
            area=CheckArea.FEEDS,
            subject=subject,
            name='Quote feed',
            status=status,
            message=f'{subject} is {status}.',
        )


class TestAlertPolicy:
    """Tests for AlertPolicy."""

    def test_failure_alerts_after_consecutive_runs_then_recovers(self):
        """Checks the debounce, the single alert while failing, and the recovery.

        Raises:
            AssertionError: A notification is missing or unexpected.
        """
        policy = AlertPolicy(_THRESHOLDS, FixedClock(0))
        policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        assert policy.take_notifications() == []
        policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        failures = policy.take_notifications()
        assert len(failures) == 1
        assert failures[0].title == 'zerodha Quote feed failed'
        assert failures[0].urgency == 'critical'
        policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        assert policy.take_notifications() == []
        policy.observe([_Results.one('zerodha', CheckStatus.OK)])
        recoveries = policy.take_notifications()
        assert [notification.title for notification in recoveries] == [
            'zerodha Quote feed recovered',
        ]
        assert recoveries[0].urgency == 'normal'
        assert policy.version == 2

    def test_single_failure_between_successes_never_alerts(self):
        """Checks that a failure that clears on the next run is ignored.

        Raises:
            AssertionError: A notification was produced.
        """
        policy = AlertPolicy(_THRESHOLDS, FixedClock(0))
        for status in (
            CheckStatus.FAILURE,
            CheckStatus.OK,
            CheckStatus.FAILURE,
            CheckStatus.WARNING,
            CheckStatus.FAILURE,
        ):
            policy.observe([_Results.one('zerodha', status)])
        assert policy.take_notifications() == []

    def test_cooldown_delays_repeat_alert(self):
        """Checks that a flapping check alerts again only after the cooldown.

        Raises:
            AssertionError: The repeat alert came too early or never.
        """
        clock = FixedClock(0)
        policy = AlertPolicy(_THRESHOLDS, clock)
        for _run in range(2):
            policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        assert len(policy.take_notifications()) == 1
        policy.observe([_Results.one('zerodha', CheckStatus.OK)])
        policy.take_notifications()
        clock.advance(60)
        for _run in range(3):
            policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        assert policy.take_notifications() == []
        clock.advance(600)
        policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        assert len(policy.take_notifications()) == 1

    def test_many_failures_share_one_notification(self):
        """Checks grouping above the threshold.

        Raises:
            AssertionError: The grouping is wrong.
        """
        policy = AlertPolicy(_THRESHOLDS, FixedClock(0))
        subjects = [
            'dhan',
            'fyers',
            'groww',
            'kotak',
            'shoonya',
            'stoxkart',
            'zerodha',
            'flattrade',
            'indmoney',
            'wisdom_capital',
        ]
        for _run in range(2):
            batch = []
            for subject in subjects:
                batch.append(_Results.one(subject, CheckStatus.FAILURE))
            policy.observe(batch)
        notifications = policy.take_notifications()
        assert len(notifications) == 1
        assert notifications[0].title == '10 checks failed'
        body_lines = notifications[0].body.split('\n')
        assert len(body_lines) == 9
        assert body_lines[-1] == 'and 2 more'

    def test_idle_forgets_alert_without_recovery(self):
        """Checks that a failing feed going idle at market close sends no recovery.

        Raises:
            AssertionError: A recovery was sent.
        """
        policy = AlertPolicy(_THRESHOLDS, FixedClock(0))
        for _run in range(2):
            policy.observe([_Results.one('groww', CheckStatus.FAILURE)])
        policy.take_notifications()
        policy.observe([_Results.one('groww', CheckStatus.IDLE)])
        policy.observe([_Results.one('groww', CheckStatus.OK)])
        assert policy.take_notifications() == []
        assert len(policy.recent_notifications()) == 1


class TestDesktopNotifier:
    """Tests for DesktopNotifier."""

    def test_send_runs_notify_send_with_arguments(self):
        """Checks the exact notify-send command.

        Raises:
            AssertionError: The command is wrong.
        """
        runner = FakeCommandRunner()
        notifier = DesktopNotifier(runner, enabled=True)
        notification = Notification(title='zerodha Quote feed failed', body='No tick.', urgency='critical', created_at=0)
        assert notifier.send(notification)
        assert runner.calls == [
            [
                'notify-send',
                '--app-name=System monitor',
                '--urgency=critical',
                '--icon=dialog-warning',
                'zerodha Quote feed failed',
                'No tick.',
            ],
        ]

    def test_send_disabled_only_logs(self):
        """Checks that a disabled notifier runs nothing.

        Raises:
            AssertionError: A command was run.
        """
        runner = FakeCommandRunner()
        notifier = DesktopNotifier(runner, enabled=False)
        notification = Notification(title='t', body='b', urgency='normal', created_at=0)
        assert not notifier.send(notification)
        assert runner.calls == []

    def test_send_reports_failure(self):
        """Checks that a failing notify-send returns False.

        Raises:
            AssertionError: The failure was not reported.
        """
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'notify-send',
            ],
            return_code=1,
            standard_error='Cannot connect to bus',
        )
        notification = Notification(title='t', body='b', urgency='normal', created_at=0)
        assert not DesktopNotifier(runner, enabled=True).send(notification)


class TestAlertDispatcher:
    """Tests for AlertDispatcher."""

    def test_dispatch_once_sends_pending_notifications(self):
        """Checks that pending notifications reach the notifier once.

        Raises:
            AssertionError: The notifications were not sent exactly once.
        """
        policy = AlertPolicy(_THRESHOLDS, FixedClock(0))
        for _run in range(2):
            policy.observe([_Results.one('zerodha', CheckStatus.FAILURE)])
        runner = FakeCommandRunner()
        dispatcher = AlertDispatcher(policy, DesktopNotifier(runner, enabled=True))
        assert asyncio.run(dispatcher.dispatch_once()) == 1
        assert asyncio.run(dispatcher.dispatch_once()) == 0
        assert len(runner.calls) == 1

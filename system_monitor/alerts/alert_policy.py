"""Decides which check results become notifications.

A check alerts when it has been a failure for several collections in a row, and not again within the cooldown. It announces its recovery when it returns to ok. Many failures noticed together share one notification. Idle checks never alert, and a check that goes idle, such as a feed at market close, is forgotten without a recovery message.

Typical usage example:

  policy = AlertPolicy(thresholds.alerts, SystemClock())
  policy.observe(outcome.results)
  for notification in policy.take_notifications():
      notifier.send(notification)
"""

import collections
import dataclasses
import threading
from typing import Any

from system_monitor.checks.check_result import CheckResult, CheckStatus
from system_monitor.configuration.thresholds import AlertThresholds
from system_monitor.utilities.clock import SystemClock

_GROUP_BODY_LINES = 8


@dataclasses.dataclass(frozen=True)
class Notification:
    """One desktop notification.

    Attributes:
        title: The one-line summary.
        body: The details, one line per check.
        urgency: "critical" for failures, "normal" for recoveries.
        created_at: When it was created, in epoch seconds.
    """

    title: str
    body: str
    urgency: str
    created_at: float


class AlertPolicy:
    """Turns streams of check results into failure and recovery notifications.

    Attributes:
        version: A number that grows whenever notifications are produced.
    """

    def __init__(
        self,
        thresholds: AlertThresholds,
        clock: SystemClock,
        history_size: int = 20,
    ):
        """Creates the policy.

        Args:
            thresholds (AlertThresholds): The consecutive failure count, cooldown and group size.
            clock (SystemClock): The source of the current time.
            history_size (int): How many produced notifications to remember for the dashboard.
        """
        self.thresholds = thresholds
        self.clock = clock
        self.version = 0
        self._lock = threading.Lock()
        self._consecutive_failures = {}
        self._alerted = set()
        self._last_alert_at = {}
        self._pending_failures = []
        self._pending_recoveries = []
        self._history = collections.deque(maxlen=history_size)

    def observe(self, results: list[CheckResult]) -> None:
        """Updates each check's alert state from its latest result.

        Args:
            results (list[CheckResult]): One collector's latest results.
        """
        now = self.clock.now()
        with self._lock:
            for result in results:
                self._observe_one(result, now)

    def take_notifications(self) -> list[Notification]:
        """Builds notifications for everything noticed since the last call, and forgets it.

        Returns:
            list[Notification]: Failure notifications first, then recovery notifications.
        """
        now = self.clock.now()
        with self._lock:
            failures = self._pending_failures
            recoveries = self._pending_recoveries
            self._pending_failures = []
            self._pending_recoveries = []
            notifications = []
            notifications.extend(self._group(failures, 'failed', 'critical', now))
            notifications.extend(self._group(recoveries, 'recovered', 'normal', now))
            for notification in notifications:
                self._history.appendleft(notification)
            if notifications:
                self.version += 1
            return notifications

    def recent_notifications(self) -> list[dict[str, Any]]:
        """Lists the notifications produced recently, newest first.

        Returns:
            list[dict[str, Any]]: Each notification's fields.
        """
        with self._lock:
            recent = []
            for notification in self._history:
                recent.append(dataclasses.asdict(notification))
            return recent

    def _observe_one(self, result: CheckResult, now: float) -> None:
        """Updates one check's alert state. The caller holds the lock.

        Args:
            result (CheckResult): The check's latest result.
            now (float): The current time, in epoch seconds.
        """
        check_id = result.check_id
        if result.status == CheckStatus.FAILURE:
            count = self._consecutive_failures.get(check_id, 0) + 1
            self._consecutive_failures[check_id] = count
            if count < self.thresholds.consecutive_failures or check_id in self._alerted:
                return
            last_alert_at = self._last_alert_at.get(check_id)
            if last_alert_at is not None and now - last_alert_at < self.thresholds.cooldown_seconds:
                return
            self._alerted.add(check_id)
            self._last_alert_at[check_id] = now
            self._pending_failures.append(result)
            return

        self._consecutive_failures[check_id] = 0
        if result.status == CheckStatus.OK and check_id in self._alerted:
            self._alerted.discard(check_id)
            self._pending_recoveries.append(result)
        elif result.status == CheckStatus.IDLE:
            self._alerted.discard(check_id)

    def _group(
        self,
        results: list[CheckResult],
        verb: str,
        urgency: str,
        now: float,
    ) -> list[Notification]:
        """Builds one notification per result, or one shared notification when there are many.

        Args:
            results (list[CheckResult]): The results to announce.
            verb (str): "failed" or "recovered".
            urgency (str): The notification urgency.
            now (float): The current time, in epoch seconds.

        Returns:
            list[Notification]: The notifications.
        """
        if not results:
            return []
        if len(results) <= self.thresholds.group_threshold:
            notifications = []
            for result in results:
                notifications.append(
                    Notification(
                        title=f'{self._label(result)} {verb}',
                        body=result.message,
                        urgency=urgency,
                        created_at=now,
                    ),
                )
            return notifications
        lines = []
        for result in results[:_GROUP_BODY_LINES]:
            lines.append(f'{self._label(result)}: {result.message}')
        hidden = len(results) - _GROUP_BODY_LINES
        if hidden > 0:
            lines.append(f'and {hidden} more')
        return [
            Notification(
                title=f'{len(results)} checks {verb}',
                body='\n'.join(lines),
                urgency=urgency,
                created_at=now,
            ),
        ]

    def _label(self, result: CheckResult) -> str:
        """Names a check for people.

        Args:
            result (CheckResult): The check.

        Returns:
            str: The subject and the check's name, such as "zerodha Quote feed".
        """
        return f'{result.subject} {result.name}'

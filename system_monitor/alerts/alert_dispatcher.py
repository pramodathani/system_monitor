"""Collects pending notifications every few seconds and sends them.

Waiting a few seconds between sends is what lets failures noticed by different collectors at nearly the same moment share one grouped notification.

Typical usage example:

  dispatcher = AlertDispatcher(policy, notifier)
  await dispatcher.run()
"""

import asyncio

from system_monitor.alerts.alert_policy import AlertPolicy
from system_monitor.alerts.desktop_notifier import DesktopNotifier


class AlertDispatcher:
    """Moves notifications from the policy to the notifier."""

    def __init__(
        self,
        policy: AlertPolicy,
        notifier: DesktopNotifier,
        interval_seconds: float = 5.0,
    ):
        """Creates the dispatcher.

        Args:
            policy (AlertPolicy): Produces notifications.
            notifier (DesktopNotifier): Shows them.
            interval_seconds (float): How long to gather notifications before sending.
        """
        self.policy = policy
        self.notifier = notifier
        self.interval_seconds = interval_seconds

    async def run(self) -> None:
        """Sends pending notifications every interval until cancelled."""
        while True:
            await asyncio.sleep(self.interval_seconds)
            await self.dispatch_once()

    async def dispatch_once(self) -> int:
        """Sends every pending notification now.

        Returns:
            int: How many notifications were taken from the policy.
        """
        notifications = self.policy.take_notifications()
        for notification in notifications:
            await asyncio.to_thread(self.notifier.send, notification)
        return len(notifications)

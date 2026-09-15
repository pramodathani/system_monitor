"""The complete document the dashboard receives, on first load and on every change.

Typical usage example:

  builder = DashboardSnapshot(state, controller, alert_policy, market_calendar, clock)
  document = builder.build()
"""

from typing import Any

from system_monitor.alerts.alert_policy import AlertPolicy
from system_monitor.controls.unit_controller import UnitController
from system_monitor.sources.market_calendar import MarketCalendar
from system_monitor.state.monitor_state import MonitorState
from system_monitor.utilities.clock import SystemClock


class DashboardSnapshot:
    """Combines check results, recent unit actions, recent notifications and market status."""

    def __init__(
        self,
        state: MonitorState,
        controller: UnitController,
        alert_policy: AlertPolicy,
        market_calendar: MarketCalendar,
        clock: SystemClock,
    ):
        """Creates the builder.

        Args:
            state (MonitorState): The check results.
            controller (UnitController): The recent unit actions.
            alert_policy (AlertPolicy): The recent notifications.
            market_calendar (MarketCalendar): Which sessions are open.
            clock (SystemClock): The source of the current time.
        """
        self.state = state
        self.controller = controller
        self.alert_policy = alert_policy
        self.market_calendar = market_calendar
        self.clock = clock

    def change_marker(self) -> tuple[int, int, int]:
        """Returns a value that changes whenever the snapshot's content may have changed.

        Returns:
            tuple[int, int, int]: A tuple (state version, controller version, alert policy version).
        """
        return (self.state.version, self.controller.version, self.alert_policy.version)

    def build(self) -> dict[str, Any]:
        """Builds the document.

        Returns:
            dict[str, Any]: The state snapshot plus "actions", "notifications", "open_sessions" and "calendar_source".
        """
        document = self.state.snapshot()
        now = self.clock.now()
        open_sessions = []
        for window in self.market_calendar.open_windows(now):
            open_sessions.append(
                {
                    'exchange': window.exchange,
                    'calendar': window.calendar,
                    'name': window.name,
                    'closes_at': window.closes_at,
                },
            )
        document['actions'] = self.controller.recent_actions()
        document['notifications'] = self.alert_policy.recent_notifications()
        document['open_sessions'] = open_sessions
        document['calendar_source'] = self.market_calendar.source()
        return document

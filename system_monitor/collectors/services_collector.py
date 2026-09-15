"""Checks that every long-running and periodic UBI service is in the state it should be.

Typical usage example:

  collector = ServicesCollector(systemd_client, inventory, thresholds.services, clock)
  outcome = collector.run_once()
"""

import collections

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import ServiceThresholds
from system_monitor.sources.systemd_client import SystemdClient
from system_monitor.sources.unit_inventory import InventoryUnit, UnitInventory, UnitKind
from system_monitor.utilities.clock import SystemClock
from system_monitor.utilities.text_formatter import TextFormatter
from system_monitor.utilities.timestamp_parser import TimestampParser

_PROPERTIES = [
    'LoadState',
    'ActiveState',
    'SubState',
    'Result',
    'NRestarts',
    'ExecMainStartTimestamp',
]


class ServicesCollector(BaseCollector):
    """Judges the systemd state of UBI's always-on services."""

    name = 'services'
    area = CheckArea.SERVICES

    def __init__(
        self,
        systemd_client: SystemdClient,
        inventory: UnitInventory,
        thresholds: ServiceThresholds,
        clock: SystemClock,
        interval_seconds: float = 5.0,
        inventory_refresh_seconds: float = 300.0,
    ):
        """Creates the collector.

        Args:
            systemd_client (SystemdClient): Reads unit properties.
            inventory (UnitInventory): The expected units; refreshed by this collector every few minutes.
            thresholds (ServiceThresholds): The restart window.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
            inventory_refresh_seconds (float): How often to read the targets' members again.
        """
        super().__init__(interval_seconds, clock)
        self.systemd_client = systemd_client
        self.inventory = inventory
        self.thresholds = thresholds
        self.inventory_refresh_seconds = inventory_refresh_seconds
        self._inventory_refreshed_at = clock.now()
        self._restart_samples = {}

    def collect(self) -> list[CheckResult]:
        """Reads every service's state and judges it.

        Returns:
            list[CheckResult]: One result per long-running or periodic unit, plus one per missing target.

        Raises:
            SystemdError: systemctl failed.
        """
        now = self.clock.now()
        if now - self._inventory_refreshed_at >= self.inventory_refresh_seconds:
            self.inventory.refresh()
            self._inventory_refreshed_at = now

        results = []
        for target in self.inventory.missing_targets():
            subject = target.removesuffix('.target')
            results.append(
                self.result(
                    target,
                    subject,
                    target,
                    CheckStatus.FAILURE,
                    'The target has no units; its services are not installed or the target is not loaded.',
                ),
            )

        units = self.inventory.units_of_kind(UnitKind.LONG_RUNNING)
        units.extend(self.inventory.units_of_kind(UnitKind.PERIODIC))
        unit_names = []
        for unit in units:
            unit_names.append(unit.name)
        properties_by_unit = self.systemd_client.show_units(unit_names, _PROPERTIES)
        for unit in units:
            properties = properties_by_unit.get(unit.name, {})
            results.append(self._judge(unit, properties, now))
        return results

    def _judge(
        self,
        unit: InventoryUnit,
        properties: dict[str, str],
        now: float,
    ) -> CheckResult:
        """Judges one unit from its properties.

        Args:
            unit (InventoryUnit): The unit.
            properties (dict[str, str]): Its systemctl show properties.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The unit's result.
        """
        load_state = properties.get('LoadState', '')
        active_state = properties.get('ActiveState', '')
        sub_state = properties.get('SubState', '')
        result_text = properties.get('Result', '')
        restarts = self._whole_number(properties.get('NRestarts', ''))
        started_at = TimestampParser.systemd_value_to_epoch(properties.get('ExecMainStartTimestamp', ''))
        recent_restarts = self._recent_restarts(unit.name, restarts, now)
        window_text = TextFormatter.duration(self.thresholds.restart_window_seconds)

        is_running = active_state == 'active' and sub_state == 'running'
        uptime = None
        if is_running and started_at is not None:
            uptime = now - started_at

        details = {
            'unit': unit.name,
            'kind': str(unit.kind),
            'load_state': load_state,
            'active_state': active_state,
            'sub_state': sub_state,
            'result': result_text,
            'restarts': restarts,
            'recent_restarts': recent_restarts,
            'started_at': started_at,
        }

        if load_state != 'loaded':
            status = CheckStatus.FAILURE
            message = f'The unit file is not loaded ({load_state or "unknown"}).'
        elif is_running and recent_restarts > 0:
            status = CheckStatus.WARNING
            message = f'Running, but restarted {recent_restarts} times in the last {window_text}.'
        elif is_running:
            status = CheckStatus.OK
            if uptime is None:
                message = 'Running.'
            else:
                message = f'Running for {TextFormatter.duration(uptime)}.'
        elif active_state == 'activating' and unit.kind == UnitKind.PERIODIC:
            status = CheckStatus.OK
            message = 'Waiting for its next run.'
        elif active_state == 'activating' and sub_state == 'auto-restart':
            status = CheckStatus.WARNING
            message = f'Exited ({result_text or "unknown reason"}) and is waiting to restart.'
        elif active_state == 'activating':
            status = CheckStatus.WARNING
            message = 'Starting.'
        elif active_state == 'deactivating':
            status = CheckStatus.WARNING
            message = 'Stopping.'
        elif active_state == 'failed':
            status = CheckStatus.FAILURE
            message = f'Failed ({result_text or "unknown reason"}) and will not restart on its own.'
        else:
            status = CheckStatus.FAILURE
            message = f'Not running ({active_state or "unknown"}/{sub_state or "unknown"}).'

        return self.result(
            unit.name,
            unit.subject,
            unit.name.removesuffix('.service'),
            status,
            message,
            value=uptime,
            details=details,
        )

    def _recent_restarts(self, unit_name: str, restarts: int, now: float) -> int:
        """Works out how many times a unit restarted within the restart window.

        systemd's NRestarts counts automatic restarts since the unit was last started by hand, so the rise across the window is the recent count.

        Args:
            unit_name (str): The unit.
            restarts (int): The current NRestarts value.
            now (float): The current time, in epoch seconds.

        Returns:
            int: The number of restarts within the window, never negative.
        """
        samples = self._restart_samples.get(unit_name)
        if samples is None:
            samples = collections.deque()
            self._restart_samples[unit_name] = samples
        samples.append((now, restarts))
        window_start = now - self.thresholds.restart_window_seconds
        while len(samples) > 1 and samples[1][0] <= window_start:
            samples.popleft()
        oldest_restarts = samples[0][1]
        return max(0, restarts - oldest_restarts)

    def _whole_number(self, text: str) -> int:
        """Reads a systemd counter.

        Args:
            text (str): The property value.

        Returns:
            int: The number, or 0 when the value is empty or not a number.
        """
        try:
            return int(text)
        except ValueError:
            return 0

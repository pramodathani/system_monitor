"""Checks UBI's daily jobs: the broker logins, the instrument download and the prices run.

Each timer is judged together with the service it starts, which has the same base name.

Typical usage example:

  collector = TimersCollector(systemd_client, inventory, clock)
  outcome = collector.run_once()
"""

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
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
    'ExecMainStatus',
    'ExecMainStartTimestamp',
    'ExecMainExitTimestamp',
    'LastTriggerUSec',
    'NextElapseUSecRealtime',
]


class TimersCollector(BaseCollector):
    """Judges each timer and the last run of its job."""

    name = 'timers'
    area = CheckArea.TIMERS

    def __init__(
        self,
        systemd_client: SystemdClient,
        inventory: UnitInventory,
        clock: SystemClock,
        interval_seconds: float = 30.0,
    ):
        """Creates the collector.

        Args:
            systemd_client (SystemdClient): Reads unit properties.
            inventory (UnitInventory): The expected units.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.systemd_client = systemd_client
        self.inventory = inventory

    def collect(self) -> list[CheckResult]:
        """Reads every timer and its service and judges them.

        Returns:
            list[CheckResult]: One result per timer.

        Raises:
            SystemdError: systemctl failed.
        """
        now = self.clock.now()
        timers = self.inventory.units_of_kind(UnitKind.TIMER)
        unit_names = []
        for timer in timers:
            unit_names.append(timer.name)
            unit_names.append(self._service_name(timer))
        properties_by_unit = self.systemd_client.show_units(unit_names, _PROPERTIES)
        results = []
        for timer in timers:
            timer_properties = properties_by_unit.get(timer.name, {})
            service_properties = properties_by_unit.get(self._service_name(timer), {})
            results.append(self._judge(timer, timer_properties, service_properties, now))
        return results

    def _judge(
        self,
        timer: InventoryUnit,
        timer_properties: dict[str, str],
        service_properties: dict[str, str],
        now: float,
    ) -> CheckResult:
        """Judges one timer and its service.

        Args:
            timer (InventoryUnit): The timer unit.
            timer_properties (dict[str, str]): The timer's properties.
            service_properties (dict[str, str]): The started service's properties.
            now (float): The current time, in epoch seconds.

        Returns:
            CheckResult: The timer's result.
        """
        service_name = self._service_name(timer)
        last_trigger = TimestampParser.systemd_value_to_epoch(timer_properties.get('LastTriggerUSec', ''))
        next_run = TimestampParser.systemd_value_to_epoch(timer_properties.get('NextElapseUSecRealtime', ''))
        last_start = TimestampParser.systemd_value_to_epoch(service_properties.get('ExecMainStartTimestamp', ''))
        last_exit = TimestampParser.systemd_value_to_epoch(service_properties.get('ExecMainExitTimestamp', ''))
        service_active_state = service_properties.get('ActiveState', '')
        service_sub_state = service_properties.get('SubState', '')
        service_result = service_properties.get('Result', '')
        exit_status = service_properties.get('ExecMainStatus', '')

        details = {
            'unit': timer.name,
            'service': service_name,
            'timer_state': timer_properties.get('ActiveState', ''),
            'service_state': f'{service_active_state}/{service_sub_state}',
            'result': service_result,
            'exit_status': exit_status,
            'last_trigger': last_trigger,
            'next_run': next_run,
            'last_start': last_start,
            'last_exit': last_exit,
        }

        next_text = 'no next run is scheduled'
        if next_run is not None:
            next_text = f'next run at {TextFormatter.india_time(next_run, now)}'

        if timer_properties.get('ActiveState', '') != 'active':
            status = CheckStatus.FAILURE
            message = 'The timer is not active, so the job will not run.'
        elif service_properties.get('LoadState', '') != 'loaded':
            status = CheckStatus.FAILURE
            message = f'The job {service_name} is not loaded.'
        elif service_sub_state == 'auto-restart':
            status = CheckStatus.WARNING
            message = f'The last attempt failed ({service_result}) and systemd will retry it.'
        elif service_active_state in ('activating', 'active', 'reloading'):
            status = CheckStatus.OK
            if last_start is None:
                message = 'Running now.'
            else:
                message = f'Running now, started {TextFormatter.duration(now - last_start)} ago.'
        elif service_result not in ('success', ''):
            status = CheckStatus.FAILURE
            message = f'The last run failed ({service_result}, exit status {exit_status}); {next_text}.'
        elif last_trigger is None:
            status = CheckStatus.IDLE
            message = f'Has not run since the timer was loaded; {next_text}.'
        elif last_exit is None or last_exit < last_trigger:
            status = CheckStatus.WARNING
            message = f'Triggered at {TextFormatter.india_time(last_trigger, now)} but has not finished.'
        else:
            status = CheckStatus.OK
            message = f'Last run finished at {TextFormatter.india_time(last_exit, now)}; {next_text}.'

        return self.result(
            timer.name,
            timer.subject,
            timer.name.removesuffix('.timer'),
            status,
            message,
            details=details,
        )

    def _service_name(self, timer: InventoryUnit) -> str:
        """Names the service a timer starts.

        Args:
            timer (InventoryUnit): The timer unit.

        Returns:
            str: The service with the timer's base name.
        """
        return timer.name.removesuffix('.timer') + '.service'

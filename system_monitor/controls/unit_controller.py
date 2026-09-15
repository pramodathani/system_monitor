"""Starts or restarts one of UBI's services on request, and remembers who asked.

Only `start` and `restart` are possible, only on `.service` units found under UBI's targets, and systemd is never waited on.

Typical usage example:

  controller = UnitController(systemd_client, inventory, SystemClock())
  action = controller.perform('unified@details.service', 'restart', '192.0.2.20')
"""

import collections
import dataclasses
import logging
import subprocess
import threading
from typing import Any

from system_monitor.sources.systemd_client import SystemdClient
from system_monitor.sources.unit_inventory import UnitInventory
from system_monitor.utilities.clock import SystemClock

_LOGGER = logging.getLogger(__name__)

ALLOWED_ACTIONS = (
    'start',
    'restart',
)


class UnitNotAllowedError(Exception):
    """The unit is not one of UBI's services, so the dashboard may not act on it."""


@dataclasses.dataclass(frozen=True)
class UnitAction:
    """One requested action and its outcome.

    Attributes:
        requested_at: When it was requested, in epoch seconds.
        unit: The unit acted on.
        action: "start" or "restart".
        address: The network address of the browser that asked.
        succeeded: Whether systemd accepted the job.
        message: What happened, in one sentence.
    """

    requested_at: float
    unit: str
    action: str
    address: str
    succeeded: bool
    message: str


class UnitController:
    """Runs allowed unit actions and keeps a short audit trail.

    Attributes:
        version: A number that grows with every recorded action.
    """

    def __init__(
        self,
        systemd_client: SystemdClient,
        inventory: UnitInventory,
        clock: SystemClock,
        history_size: int = 50,
    ):
        """Creates the controller.

        Args:
            systemd_client (SystemdClient): Runs the systemctl commands.
            inventory (UnitInventory): The units that may be acted on.
            clock (SystemClock): The source of the current time.
            history_size (int): How many recent actions to remember.
        """
        self.systemd_client = systemd_client
        self.inventory = inventory
        self.clock = clock
        self.version = 0
        self._actions = collections.deque(maxlen=history_size)
        self._lock = threading.Lock()

    def perform(self, unit_name: str, action: str, address: str) -> UnitAction:
        """Asks systemd to start or restart a UBI service.

        Args:
            unit_name (str): The exact unit name, such as "zerodha@quotes.service".
            action (str): "start" or "restart".
            address (str): The network address of the browser that asked, for the audit trail.

        Returns:
            UnitAction: The recorded action.

        Raises:
            ValueError: The action is not "start" or "restart".
            UnitNotAllowedError: The unit is not a service under one of UBI's targets.
        """
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f'Unsupported unit action: {action!r}')
        if not unit_name.endswith('.service') or not self.inventory.has_unit(unit_name):
            raise UnitNotAllowedError(f'Not a unified_broker_interface service: {unit_name!r}')

        try:
            result = self.systemd_client.run_unit_action(action, unit_name)
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            succeeded = False
            message = f'systemctl could not be run: {error}'
        else:
            succeeded = result.return_code == 0
            if succeeded:
                message = f'systemd accepted the {action} job.'
            else:
                message = f'systemctl {action} failed (exit {result.return_code}): {result.standard_error.strip()}'

        recorded = UnitAction(
            requested_at=self.clock.now(),
            unit=unit_name,
            action=action,
            address=address,
            succeeded=succeeded,
            message=message,
        )
        _LOGGER.info('Unit action %s %s requested from %s: %s', action, unit_name, address, message)
        with self._lock:
            self._actions.appendleft(recorded)
            self.version += 1
        return recorded

    def recent_actions(self) -> list[dict[str, Any]]:
        """Lists the remembered actions, newest first.

        Returns:
            list[dict[str, Any]]: Each action's fields.
        """
        with self._lock:
            actions = []
            for recorded in self._actions:
                actions.append(dataclasses.asdict(recorded))
            return actions

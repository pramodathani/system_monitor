"""The list of UBI's systemd units the monitor expects to exist.

The subjects are the folder names under UBI's `services/` directory, such as "zerodha" and "unified", and each subject's units are the members of its systemd target, such as `zerodha.target`. Reading the targets rather than listing running units means a unit that stopped or was never started still appears, as a failure.

Typical usage example:

  inventory = UnitInventory(systemd_client, Path('.../unified_broker_interface/services'))
  inventory.refresh()
  for unit in inventory.units():
      print(unit.name, unit.kind)
"""

import dataclasses
import enum
import threading
from pathlib import Path

from system_monitor.sources.systemd_client import SystemdClient

UNIFIED_SUBJECT = 'unified'


class UnitKind(enum.StrEnum):
    """How a unit is expected to behave."""

    LONG_RUNNING = 'long_running'
    PERIODIC = 'periodic'
    SCHEDULED = 'scheduled'
    TIMER = 'timer'


@dataclasses.dataclass(frozen=True)
class InventoryUnit:
    """One expected unit.

    Attributes:
        name: The full unit name, such as "zerodha@quotes.service".
        subject: The broker name, or "unified".
        kind: How the unit is expected to behave.
    """

    name: str
    subject: str
    kind: UnitKind


class UnitInventory:
    """Discovers and remembers the units under UBI's targets."""

    def __init__(self, systemd_client: SystemdClient, services_directory: Path):
        """Creates an empty inventory.

        Args:
            systemd_client (SystemdClient): Lists each target's members.
            services_directory (Path): UBI's `services/` directory, whose folder names are the subjects.
        """
        self.systemd_client = systemd_client
        self.services_directory = services_directory
        self._lock = threading.Lock()
        self._units = []
        self._missing_targets = []
        self._subjects = []

    def refresh(self) -> None:
        """Reads the subjects and every target's members again.

        Raises:
            FileNotFoundError: UBI's services directory does not exist.
            SystemdError: systemctl failed.
        """
        subjects = self._read_subjects()
        units = []
        missing_targets = []
        for subject in subjects:
            members = self.systemd_client.list_target_members(f'{subject}.target')
            if not members:
                missing_targets.append(f'{subject}.target')
                continue
            for member in members:
                units.append(
                    InventoryUnit(
                        name=member,
                        subject=subject,
                        kind=self._kind_of(member, members),
                    ),
                )
        with self._lock:
            self._subjects = subjects
            self._units = units
            self._missing_targets = missing_targets

    def units(self) -> list[InventoryUnit]:
        """Lists every expected unit.

        Returns:
            list[InventoryUnit]: The units found at the last refresh.
        """
        with self._lock:
            return list(self._units)

    def units_of_kind(self, kind: UnitKind) -> list[InventoryUnit]:
        """Lists the expected units of one kind.

        Args:
            kind (UnitKind): The kind to keep.

        Returns:
            list[InventoryUnit]: The matching units.
        """
        matching = []
        for unit in self.units():
            if unit.kind == kind:
                matching.append(unit)
        return matching

    def find(self, unit_name: str) -> InventoryUnit | None:
        """Looks up one unit by exact name.

        Args:
            unit_name (str): The full unit name.

        Returns:
            InventoryUnit | None: The unit, or None when it is not in the inventory.
        """
        for unit in self.units():
            if unit.name == unit_name:
                return unit
        return None

    def has_unit(self, unit_name: str) -> bool:
        """Checks whether a unit is in the inventory.

        Args:
            unit_name (str): The full unit name.

        Returns:
            bool: True when the unit was found under one of UBI's targets.
        """
        return self.find(unit_name) is not None

    def subjects(self) -> list[str]:
        """Lists every subject, brokers first and "unified" last.

        Returns:
            list[str]: The subject names.
        """
        with self._lock:
            return list(self._subjects)

    def brokers(self) -> list[str]:
        """Lists the broker subjects.

        Returns:
            list[str]: Every subject except "unified".
        """
        brokers = []
        for subject in self.subjects():
            if subject != UNIFIED_SUBJECT:
                brokers.append(subject)
        return brokers

    def missing_targets(self) -> list[str]:
        """Lists targets that had no members at the last refresh.

        Returns:
            list[str]: Target names, such as "kotak.target".
        """
        with self._lock:
            return list(self._missing_targets)

    def _read_subjects(self) -> list[str]:
        """Reads the subject names from UBI's services directory.

        Returns:
            list[str]: The broker folder names sorted, followed by "unified" when present.

        Raises:
            FileNotFoundError: The services directory does not exist.
        """
        if not self.services_directory.is_dir():
            raise FileNotFoundError(f'UBI services directory not found: {self.services_directory}')
        brokers = []
        has_unified = False
        for path in self.services_directory.iterdir():
            if not path.is_dir():
                continue
            if path.name == UNIFIED_SUBJECT:
                has_unified = True
            else:
                brokers.append(path.name)
        subjects = sorted(brokers)
        if has_unified:
            subjects.append(UNIFIED_SUBJECT)
        return subjects

    def _kind_of(self, unit_name: str, members: list[str]) -> UnitKind:
        """Decides how a unit is expected to behave.

        Args:
            unit_name (str): The unit name.
            members (list[str]): Every member of the unit's target.

        Returns:
            UnitKind: TIMER for a timer, SCHEDULED for a service a timer in the same target starts, PERIODIC for a historical prices worker, and LONG_RUNNING otherwise.
        """
        if unit_name.endswith('.timer'):
            return UnitKind.TIMER
        base_name = unit_name.removesuffix('.service')
        if base_name + '.timer' in members:
            return UnitKind.SCHEDULED
        if base_name.endswith('-historical-prices'):
            return UnitKind.PERIODIC
        return UnitKind.LONG_RUNNING

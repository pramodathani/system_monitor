"""Test doubles shared by the test modules."""

import datetime
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

from system_monitor.sources.command_runner import CommandResult
from system_monitor.sources.unit_inventory import UnitInventory
from system_monitor.utilities.timestamp_parser import INDIA_TIMEZONE


class FixedClock:
    """A clock that stays at a set moment until moved."""

    def __init__(self, epoch: float):
        """Creates the clock.

        Args:
            epoch (float): The moment the clock shows, in epoch seconds.
        """
        self.epoch = epoch

    @classmethod
    def at_india_time(
        cls,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int = 0,
        second: int = 0,
    ) -> FixedClock:
        """Creates a clock at an India date and time.

        Args:
            year (int): The year.
            month (int): The month.
            day (int): The day of the month.
            hour (int): The hour.
            minute (int): The minute.
            second (int): The second.

        Returns:
            FixedClock: The clock at that moment.
        """
        moment = datetime.datetime(year, month, day, hour, minute, second, tzinfo=INDIA_TIMEZONE)
        return cls(moment.timestamp())

    def now(self) -> float:
        """Reads the set moment.

        Returns:
            float: The moment in epoch seconds.
        """
        return self.epoch

    def advance(self, seconds: float) -> None:
        """Moves the clock forward.

        Args:
            seconds (float): How far to move.
        """
        self.epoch += seconds


class FakeCommandRunner:
    """A command runner that answers from prepared responses and records every call."""

    def __init__(self):
        """Creates a runner with no prepared responses."""
        self.calls = []
        self._responses = []

    def add_response(
        self,
        argument_prefix: Sequence[str],
        standard_output: str = '',
        return_code: int = 0,
        standard_error: str = '',
    ) -> None:
        """Prepares the answer for commands starting with some arguments.

        Later responses for the same prefix take precedence.

        Args:
            argument_prefix (Sequence[str]): The leading arguments a command must have.
            standard_output (str): The output to return.
            return_code (int): The exit status to return.
            standard_error (str): The error output to return.
        """
        self._responses.insert(
            0,
            (
                list(argument_prefix),
                CommandResult(return_code, standard_output, standard_error),
            ),
        )

    def run(
        self,
        arguments: Sequence[str],
        timeout_seconds: float = 10.0,
    ) -> CommandResult:
        """Records a command and returns its prepared answer.

        Args:
            arguments (Sequence[str]): The command and its arguments.
            timeout_seconds (float): Ignored.

        Returns:
            CommandResult: The prepared answer, or an empty successful result when none matches.
        """
        del timeout_seconds
        arguments = list(arguments)
        self.calls.append(arguments)
        for prefix, result in self._responses:
            if arguments[:len(prefix)] == prefix:
                return result
        return CommandResult(0, '', '')


class FakeRedisReader:
    """An in-memory stand-in for RedisReader."""

    def __init__(self):
        """Creates an empty store."""
        self.strings = {}
        self.hashes = {}
        self.streams = {}
        self.groups = {}
        self.ping_result = 1.0
        self.ping_error = None

    def set_json(self, key: str, document: object) -> None:
        """Stores a JSON document under a string key.

        Args:
            key (str): The key.
            document (object): The document to store as JSON.
        """
        self.strings[key] = json.dumps(document)

    def set_hash_json(self, key: str, field: str, document: object) -> None:
        """Stores a JSON document in a hash field.

        Args:
            key (str): The hash key.
            field (str): The field.
            document (object): The document to store as JSON.
        """
        self.hashes.setdefault(key, {})[field] = json.dumps(document)

    def ping_milliseconds(self) -> float:
        """Answers a ping.

        Returns:
            float: The prepared latency.

        Raises:
            Exception: The prepared ping error, when set.
        """
        if self.ping_error is not None:
            raise self.ping_error
        return self.ping_result

    def get_text(self, key: str) -> str | None:
        """Reads a string key.

        Args:
            key (str): The key.

        Returns:
            str | None: The value or None.
        """
        return self.strings.get(key)

    def get_json(self, key: str) -> object:
        """Reads a JSON string key.

        Args:
            key (str): The key.

        Returns:
            object: The parsed document or None.
        """
        text = self.strings.get(key)
        if text is None:
            return None
        return json.loads(text)

    def hash_get_json(self, key: str, field: str) -> object:
        """Reads a JSON hash field.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            object: The parsed document or None.
        """
        text = self.hashes.get(key, {}).get(field)
        if text is None:
            return None
        return json.loads(text)

    def hash_length(self, key: str) -> int:
        """Counts a hash's fields.

        Args:
            key (str): The hash key.

        Returns:
            int: The number of fields.
        """
        return len(self.hashes.get(key, {}))

    def scan_hash(self, key: str, batch_size: int = 500) -> Iterator[tuple[str, str]]:
        """Walks a hash.

        Args:
            key (str): The hash key.
            batch_size (int): Ignored.

        Yields:
            tuple[str, str]: Each field and value.
        """
        del batch_size
        yield from self.hashes.get(key, {}).items()

    def stream_info(self, key: str) -> dict | None:
        """Reads prepared stream information.

        Args:
            key (str): The stream key.

        Returns:
            dict | None: The information or None.
        """
        return self.streams.get(key)

    def stream_groups(self, key: str) -> list[dict]:
        """Reads prepared consumer groups.

        Args:
            key (str): The stream key.

        Returns:
            list[dict]: The groups.
        """
        return self.groups.get(key, [])


class FakeSystemdClient:
    """A stand-in for SystemdClient answering from prepared properties."""

    def __init__(self, members_by_target: dict[str, list[str]] | None = None):
        """Creates the client.

        Args:
            members_by_target (dict[str, list[str]] | None): Each target's member units.
        """
        self.members_by_target = members_by_target or {}
        self.properties = {}
        self.actions = []

    def list_target_members(self, target: str) -> list[str]:
        """Lists a target's prepared members.

        Args:
            target (str): The target.

        Returns:
            list[str]: The members.
        """
        return list(self.members_by_target.get(target, []))

    def show_units(self, unit_names: Sequence[str], property_names: Sequence[str]) -> dict[str, dict[str, str]]:
        """Returns the prepared properties of the requested units.

        Args:
            unit_names (Sequence[str]): The units.
            property_names (Sequence[str]): Ignored.

        Returns:
            dict[str, dict[str, str]]: The properties of units that have any.
        """
        del property_names
        shown = {}
        for unit_name in unit_names:
            if unit_name in self.properties:
                shown[unit_name] = dict(self.properties[unit_name], Id=unit_name)
        return shown

    def run_unit_action(self, action: str, unit_name: str) -> CommandResult:
        """Records an action.

        Args:
            action (str): The action.
            unit_name (str): The unit.

        Returns:
            CommandResult: A successful result.
        """
        self.actions.append((action, unit_name))
        return CommandResult(0, '', '')


class FakeUnitInventory(UnitInventory):
    """A UnitInventory whose subjects and members are given directly."""

    def __init__(self, members_by_subject: dict[str, list[str]]):
        """Creates and refreshes the inventory.

        Args:
            members_by_subject (dict[str, list[str]]): Each subject's member units, with "unified" listed last if present.
        """
        members_by_target = {}
        for subject, members in members_by_subject.items():
            members_by_target[f'{subject}.target'] = members
        super().__init__(FakeSystemdClient(members_by_target), Path('/nonexistent'))
        self._given_subjects = list(members_by_subject)
        self.refresh()

    def _read_subjects(self) -> list[str]:
        """Returns the given subjects.

        Returns:
            list[str]: The subjects.
        """
        return list(self._given_subjects)

"""Test doubles shared by the test modules."""

import datetime
from collections.abc import Sequence

from system_monitor.sources.command_runner import CommandResult
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

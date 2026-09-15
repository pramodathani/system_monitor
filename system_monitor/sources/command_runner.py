"""Runs external commands such as systemctl, journalctl, docker and notify-send.

Every command is passed as a list of arguments and never through a shell, so a unit name can never be read as shell syntax.

Typical usage example:

  runner = CommandRunner()
  result = runner.run(['systemctl', '--user', 'is-system-running'])
"""

import dataclasses
import subprocess
from collections.abc import Sequence


@dataclasses.dataclass(frozen=True)
class CommandResult:
    """The outcome of one finished command.

    Attributes:
        return_code: The command's exit status.
        standard_output: Everything the command wrote to standard output.
        standard_error: Everything the command wrote to standard error.
    """

    return_code: int
    standard_output: str
    standard_error: str


class CommandRunner:
    """Runs a command and waits for it to finish."""

    def run(
        self,
        arguments: Sequence[str],
        timeout_seconds: float = 10.0,
    ) -> CommandResult:
        """Runs a command without a shell.

        Args:
            arguments (Sequence[str]): The program followed by its arguments.
            timeout_seconds (float): How long to wait before giving up.

        Returns:
            CommandResult: The exit status and output of the command.

        Raises:
            FileNotFoundError: The program does not exist.
            subprocess.TimeoutExpired: The command did not finish in time.
        """
        completed = subprocess.run(
            list(arguments),
            capture_output=True,
            text=True,
            errors='replace',
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            return_code=completed.returncode,
            standard_output=completed.stdout,
            standard_error=completed.stderr,
        )

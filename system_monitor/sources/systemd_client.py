"""Reads and controls systemd user units through systemctl.

Typical usage example:

  client = SystemdClient(CommandRunner())
  members = client.list_target_members('zerodha.target')
  properties = client.show_units(members, ['ActiveState', 'SubState'])
"""

from collections.abc import Sequence

from system_monitor.sources.command_runner import CommandResult, CommandRunner


class SystemdError(Exception):
    """A systemctl command failed."""


class SystemdClient:
    """A thin wrapper over `systemctl --user`."""

    def __init__(self, command_runner: CommandRunner):
        """Creates the client.

        Args:
            command_runner (CommandRunner): Runs the systemctl commands.
        """
        self.command_runner = command_runner

    def list_target_members(self, target: str) -> list[str]:
        """Lists the units a target pulls in.

        Args:
            target (str): The target name, such as "zerodha.target".

        Returns:
            list[str]: The member unit names, in systemctl's order. The list is empty when the target does not exist.

        Raises:
            SystemdError: systemctl exited with an error.
        """
        result = self.command_runner.run(
            [
                'systemctl',
                '--user',
                'list-dependencies',
                target,
                '--plain',
                '--no-pager',
                '--no-legend',
            ],
        )
        self._raise_on_error(result, f'list-dependencies {target}')
        members = []
        lines = result.standard_output.splitlines()
        for line in lines[1:]:
            name = line.strip()
            if name:
                members.append(name)
        return members

    def show_units(
        self,
        unit_names: Sequence[str],
        property_names: Sequence[str],
    ) -> dict[str, dict[str, str]]:
        """Reads properties of several units in one systemctl call.

        Timestamps are printed as "@<epoch seconds>".

        Args:
            unit_names (Sequence[str]): The units to read.
            property_names (Sequence[str]): The properties to read, such as "ActiveState".

        Returns:
            dict[str, dict[str, str]]: Each unit's properties, keyed by unit name.

        Raises:
            SystemdError: systemctl exited with an error.
        """
        if not unit_names:
            return {}
        requested = [
            'Id',
            *property_names,
        ]
        arguments = [
            'systemctl',
            '--user',
            'show',
            '--timestamp=unix',
            '--no-pager',
            '--property=' + ','.join(requested),
        ]
        arguments.extend(unit_names)
        result = self.command_runner.run(arguments, timeout_seconds=20.0)
        self._raise_on_error(result, 'show')
        return self._parse_show_output(result.standard_output)

    def run_unit_action(self, action: str, unit_name: str) -> CommandResult:
        """Asks systemd to start or restart a unit without waiting for it.

        Args:
            action (str): "start" or "restart".
            unit_name (str): The unit to act on.

        Returns:
            CommandResult: The outcome of the systemctl command.

        Raises:
            ValueError: The action is not "start" or "restart".
        """
        if action not in ('start', 'restart'):
            raise ValueError(f'Unsupported unit action: {action!r}')
        return self.command_runner.run(
            [
                'systemctl',
                '--user',
                action,
                '--no-block',
                unit_name,
            ],
        )

    def _parse_show_output(self, output: str) -> dict[str, dict[str, str]]:
        """Splits `systemctl show` output into one dictionary per unit.

        Args:
            output (str): The command's standard output, with units separated by blank lines.

        Returns:
            dict[str, dict[str, str]]: Each unit's properties, keyed by its Id.
        """
        units = {}
        current = {}
        for line in output.splitlines():
            if not line.strip():
                self._store_block(units, current)
                current = {}
                continue
            key, _, value = line.partition('=')
            current[key] = value
        self._store_block(units, current)
        return units

    def _store_block(
        self,
        units: dict[str, dict[str, str]],
        block: dict[str, str],
    ) -> None:
        """Adds one parsed unit block to the result when it has an Id.

        Args:
            units (dict[str, dict[str, str]]): The result being built, changed in place.
            block (dict[str, str]): One unit's properties.
        """
        if 'Id' in block:
            units[block['Id']] = block

    def _raise_on_error(self, result: CommandResult, description: str) -> None:
        """Turns a failed command into an exception.

        Args:
            result (CommandResult): The command outcome.
            description (str): What was being run, for the message.

        Raises:
            SystemdError: The command exited with a non-zero status.
        """
        if result.return_code != 0:
            raise SystemdError(f'systemctl {description} failed (exit {result.return_code}): {result.standard_error.strip()}')

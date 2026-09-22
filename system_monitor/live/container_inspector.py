"""What Docker knows about the containers the three data stores run in.

The stores themselves report how long they have been up, but only Docker knows when the container around them was last started, how many times it has been restarted and what its own health check currently says. That is what makes "last reboot" answerable: a store's uptime resets silently on a restart, whereas the container's start time is a date and a time.

The compose service label is what ties a container to a store, rather than its name, because the container's name carries the project name and an instance number that a rename would change.

Typical usage example:

  inspector = ContainerInspector(CommandRunner())
  containers = inspector.by_service('unified_broker_interface')
"""

import datetime
from typing import Any

from system_monitor.sources.command_runner import CommandRunner
from system_monitor.sources.docker_client import DockerError

_INSPECT_FORMAT = (
    '{{.Name}}\t'
    '{{.State.Status}}\t'
    '{{.State.StartedAt}}\t'
    '{{.RestartCount}}\t'
    '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}\t'
    '{{index .Config.Labels "com.docker.compose.service"}}'
)


class ContainerInspector:
    """Reads the state of a compose project's containers, keyed by service name."""

    def __init__(self, command_runner: CommandRunner):
        """Creates the inspector.

        Args:
            command_runner (CommandRunner): Runs the docker commands.
        """
        self.command_runner = command_runner

    def by_service(self, project_name: str) -> dict[str, dict[str, Any]]:
        """Describes every container of a compose project, keyed by its compose service.

        Args:
            project_name (str): The compose project name.

        Returns:
            dict[str, dict[str, Any]]: Each service name mapped to the keys "name", "state", "started_at", "restart_count" and "health".

        Raises:
            DockerError: A docker command exited with an error.
            FileNotFoundError: docker is not installed.
            subprocess.TimeoutExpired: A docker command did not finish in time.
        """
        names = self._container_names(project_name)
        if not names:
            return {}
        result = self.command_runner.run(
            [
                'docker',
                'inspect',
                '--format',
                _INSPECT_FORMAT,
                *names,
            ],
        )
        if result.return_code != 0:
            raise DockerError(f'docker inspect failed (exit {result.return_code}): {result.standard_error.strip()}')
        containers = {}
        for line in result.standard_output.splitlines():
            container = self._parse(line)
            if container is None:
                continue
            containers[container.pop('service')] = container
        return containers

    def _container_names(self, project_name: str) -> list[str]:
        """Lists the container names belonging to a compose project.

        Args:
            project_name (str): The compose project name.

        Returns:
            list[str]: The names, running or not.

        Raises:
            DockerError: docker ps exited with an error.
            FileNotFoundError: docker is not installed.
            subprocess.TimeoutExpired: docker ps did not finish in time.
        """
        result = self.command_runner.run(
            [
                'docker',
                'ps',
                '--all',
                '--filter',
                f'label=com.docker.compose.project={project_name}',
                '--format',
                '{{.Names}}',
            ],
        )
        if result.return_code != 0:
            raise DockerError(f'docker ps failed (exit {result.return_code}): {result.standard_error.strip()}')
        names = []
        for line in result.standard_output.splitlines():
            if line.strip():
                names.append(line.strip())
        return names

    def _parse(self, line: str) -> dict[str, Any] | None:
        """Reads one line of the inspect output.

        Args:
            line (str): One tab-separated line.

        Returns:
            dict[str, Any] | None: The container's state with its service name, or None when the line is not one.
        """
        parts = line.split('\t')
        if len(parts) != 6:
            return None
        name, state, started_at, restart_count, health, service = parts
        if not service:
            return None
        return {
            'service': service,
            'name': name.lstrip('/'),
            'state': state,
            'started_at': self._epoch(started_at),
            'restart_count': self._integer(restart_count),
            'health': None if health == 'none' else health,
        }

    def _epoch(self, text: str) -> float | None:
        """Reads Docker's start time into epoch seconds.

        Args:
            text (str): The time as Docker writes it, such as "2026-09-22T06:23:45.256732377Z".

        Returns:
            float | None: Epoch seconds, or None when the text is not a time or the container has never started.
        """
        cleaned = text.strip()
        if not cleaned or cleaned.startswith('0001-01-01'):
            return None
        if cleaned.endswith('Z'):
            cleaned = f'{cleaned[:-1]}+00:00'
        head, separator, tail = cleaned.partition('.')
        if separator:
            digits = ''
            offset = ''
            for position, character in enumerate(tail):
                if character.isdigit():
                    digits += character
                else:
                    offset = tail[position:]
                    break
            cleaned = f'{head}.{digits[:6]}{offset}'
        try:
            return datetime.datetime.fromisoformat(cleaned).timestamp()
        except ValueError:
            return None

    def _integer(self, text: str) -> int | None:
        """Reads a count that Docker wrote as text.

        Args:
            text (str): The count.

        Returns:
            int | None: The number, or None when the text is not one.
        """
        try:
            return int(text.strip())
        except ValueError:
            return None

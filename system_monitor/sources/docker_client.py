"""Lists the Docker containers of UBI's compose project.

Typical usage example:

  client = DockerClient(CommandRunner())
  for container in client.project_containers('unified_broker_interface'):
      print(container.name, container.state)
"""

import dataclasses
import json
import operator

from system_monitor.sources.command_runner import CommandRunner


class DockerError(Exception):
    """A docker command failed."""


@dataclasses.dataclass(frozen=True)
class ContainerStatus:
    """The state of one container.

    Attributes:
        name: The container name, such as "unified_broker_interface-redis-1".
        state: Docker's state word, such as "running" or "exited".
        status: Docker's status text, such as "Up 4 days (healthy)".
    """

    name: str
    state: str
    status: str

    @property
    def is_unhealthy(self) -> bool:
        """Whether Docker's health check reports the container as unhealthy."""
        return '(unhealthy)' in self.status


class DockerClient:
    """A thin wrapper over `docker ps`."""

    def __init__(self, command_runner: CommandRunner):
        """Creates the client.

        Args:
            command_runner (CommandRunner): Runs the docker commands.
        """
        self.command_runner = command_runner

    def project_containers(self, project_name: str) -> list[ContainerStatus]:
        """Lists every container of a compose project, running or not.

        Args:
            project_name (str): The compose project name.

        Returns:
            list[ContainerStatus]: The containers, sorted by name.

        Raises:
            DockerError: docker exited with an error.
            FileNotFoundError: docker is not installed.
        """
        result = self.command_runner.run(
            [
                'docker',
                'ps',
                '--all',
                '--filter',
                f'label=com.docker.compose.project={project_name}',
                '--format',
                '{{json .}}',
            ],
        )
        if result.return_code != 0:
            raise DockerError(f'docker ps failed (exit {result.return_code}): {result.standard_error.strip()}')
        containers = []
        for line in result.standard_output.splitlines():
            if not line.strip():
                continue
            document = json.loads(line)
            containers.append(
                ContainerStatus(
                    name=document.get('Names', ''),
                    state=document.get('State', ''),
                    status=document.get('Status', ''),
                ),
            )
        containers.sort(key=operator.attrgetter('name'))
        return containers

"""The three data stores side by side: whether each is online, when it last restarted and how it is doing.

Each store answers in its own vocabulary. Redis and MongoDB report how many seconds they have been up, while PostgreSQL reports the moment it started, so both are converted here into the same pair of values and every store ends up carrying a start time and an uptime whichever it gave.

The container each store runs in is looked up once and attached to its store, because the container's start time is the honest answer to "when did this last reboot": a store restarted inside a container that kept running has a short uptime and an old container, and the page should be able to show both.

Typical usage example:

  health = DatabaseHealth(redis_health, mongodb_health, timescaledb_health, inspector, clock)
  reading = health.read()
"""

import subprocess
from typing import Any

from system_monitor.live.container_inspector import ContainerInspector
from system_monitor.live.mongodb_health import MongodbHealth
from system_monitor.live.redis_health import RedisHealth
from system_monitor.live.timescaledb_health import TimescaledbHealth
from system_monitor.sources.docker_client import DockerError
from system_monitor.utilities.clock import SystemClock

_COMPOSE_PROJECT = 'unified_broker_interface'


class DatabaseHealth:
    """Reads all three stores and their containers in one go."""

    def __init__(
        self,
        redis_health: RedisHealth,
        mongodb_health: MongodbHealth,
        timescaledb_health: TimescaledbHealth,
        container_inspector: ContainerInspector,
        clock: SystemClock,
    ):
        """Creates the reader.

        Args:
            redis_health (RedisHealth): Reads Redis.
            mongodb_health (MongodbHealth): Reads MongoDB.
            timescaledb_health (TimescaledbHealth): Reads TimescaleDB.
            container_inspector (ContainerInspector): Reads the containers the stores run in.
            clock (SystemClock): The source of the current time.
        """
        self.redis_health = redis_health
        self.mongodb_health = mongodb_health
        self.timescaledb_health = timescaledb_health
        self.container_inspector = container_inspector
        self.clock = clock

    def read(self) -> dict[str, Any]:
        """Reads every store and attaches its container.

        Returns:
            dict[str, Any]: The keys "read_at", "docker_error" and "stores", where "stores" is one reading per store in the order Redis, MongoDB, TimescaleDB.
        """
        now = self.clock.now()
        containers, docker_error = self._containers()
        stores = []
        for reading in (
            self.redis_health.read(),
            self.mongodb_health.read(),
            self.timescaledb_health.read(),
        ):
            stores.append(self._complete(reading, containers, now))
        return {
            'read_at': now,
            'docker_error': docker_error,
            'stores': stores,
        }

    def _containers(self) -> tuple[dict[str, dict[str, Any]], str | None]:
        """Reads the compose project's containers, tolerating a Docker that cannot be read.

        Returns:
            tuple[dict[str, dict[str, Any]], str | None]: The containers by service name, and the reason Docker could not be read, which is None when it could.
        """
        try:
            return self.container_inspector.by_service(_COMPOSE_PROJECT), None
        except (DockerError, FileNotFoundError, subprocess.TimeoutExpired) as error:
            return {}, f'{type(error).__name__}: {error}'

    def _complete(
        self,
        reading: dict[str, Any],
        containers: dict[str, dict[str, Any]],
        now: float,
    ) -> dict[str, Any]:
        """Fills in whichever of the start time and the uptime the store did not give, and attaches its container.

        Args:
            reading (dict[str, Any]): One store's own reading.
            containers (dict[str, dict[str, Any]]): The containers by compose service name.
            now (float): The current time, in epoch seconds.

        Returns:
            dict[str, Any]: The reading with "started_at", "uptime_seconds" and "container" all present.
        """
        started_at = reading.get('started_at')
        uptime_seconds = reading.get('uptime_seconds')
        if started_at is None and uptime_seconds is not None:
            started_at = now - float(uptime_seconds)
        if uptime_seconds is None and started_at is not None:
            uptime_seconds = now - float(started_at)
        reading['started_at'] = started_at
        reading['uptime_seconds'] = uptime_seconds
        reading['container'] = containers.get(reading['name'])
        return reading

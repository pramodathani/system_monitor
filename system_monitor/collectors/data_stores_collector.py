"""Checks that UBI's stores, REST API and Docker containers are reachable and quick.

Typical usage example:

  collector = DataStoresCollector(redis_reader, mongo_connection, postgres_probe, rest_api_probe, docker_client, thresholds.data_stores, clock)
  outcome = collector.run_once()
"""

import subprocess

import httpx
import psycopg2
import pymongo.errors
import redis

from system_monitor.checks.check_result import CheckArea, CheckResult, CheckStatus
from system_monitor.collectors.base_collector import BaseCollector
from system_monitor.configuration.thresholds import DataStoreThresholds
from system_monitor.sources.docker_client import DockerClient, DockerError
from system_monitor.sources.mongo_connection import MongoConnection
from system_monitor.sources.postgres_probe import PostgresProbe
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.rest_api_probe import RestApiProbe
from system_monitor.utilities.clock import SystemClock

_PLATFORM = 'platform'
_COMPOSE_PROJECT = 'unified_broker_interface'


class DataStoresCollector(BaseCollector):
    """Judges reachability and response time of the shared infrastructure."""

    name = 'data_stores'
    area = CheckArea.DATA_STORES

    def __init__(
        self,
        redis_reader: RedisReader,
        mongo_connection: MongoConnection,
        postgres_probe: PostgresProbe,
        rest_api_probe: RestApiProbe,
        docker_client: DockerClient,
        thresholds: DataStoreThresholds,
        clock: SystemClock,
        interval_seconds: float = 15.0,
    ):
        """Creates the collector.

        Args:
            redis_reader (RedisReader): Pings Redis.
            mongo_connection (MongoConnection): Pings MongoDB.
            postgres_probe (PostgresProbe): Queries TimescaleDB.
            rest_api_probe (RestApiProbe): Calls the REST API's greeting route.
            docker_client (DockerClient): Lists UBI's containers.
            thresholds (DataStoreThresholds): The slow response limit.
            clock (SystemClock): The source of the current time.
            interval_seconds (float): How long to wait between runs.
        """
        super().__init__(interval_seconds, clock)
        self.redis_reader = redis_reader
        self.mongo_connection = mongo_connection
        self.postgres_probe = postgres_probe
        self.rest_api_probe = rest_api_probe
        self.docker_client = docker_client
        self.thresholds = thresholds

    def collect(self) -> list[CheckResult]:
        """Probes every store and container.

        Returns:
            list[CheckResult]: One result per store, one for the REST API and one per container.
        """
        results = [
            self._probe_redis(),
            self._probe_mongodb(),
            self._probe_postgres(),
            self._probe_rest_api(),
        ]
        results.extend(self._containers())
        return results

    def _probe_redis(self) -> CheckResult:
        """Pings Redis.

        Returns:
            CheckResult: The Redis result.
        """
        try:
            milliseconds = self.redis_reader.ping_milliseconds()
        except redis.RedisError as error:
            return self._unreachable('redis', 'Redis', error)
        return self._timed('redis', 'Redis', milliseconds)

    def _probe_mongodb(self) -> CheckResult:
        """Pings MongoDB.

        Returns:
            CheckResult: The MongoDB result.
        """
        try:
            milliseconds = self.mongo_connection.ping_milliseconds()
        except pymongo.errors.PyMongoError as error:
            return self._unreachable('mongodb', 'MongoDB', error)
        return self._timed('mongodb', 'MongoDB', milliseconds)

    def _probe_postgres(self) -> CheckResult:
        """Runs SELECT 1 on TimescaleDB.

        Returns:
            CheckResult: The TimescaleDB result.
        """
        try:
            milliseconds = self.postgres_probe.select_one_milliseconds()
        except psycopg2.Error as error:
            return self._unreachable('timescaledb', 'TimescaleDB', error)
        return self._timed('timescaledb', 'TimescaleDB', milliseconds)

    def _probe_rest_api(self) -> CheckResult:
        """Calls the REST API's unauthenticated greeting route.

        Returns:
            CheckResult: The REST API result.
        """
        try:
            milliseconds = self.rest_api_probe.greeting_milliseconds()
        except httpx.HTTPError as error:
            return self._unreachable('rest_api', 'REST API', error)
        return self._timed('rest_api', 'REST API', milliseconds)

    def _containers(self) -> list[CheckResult]:
        """Judges each of UBI's Docker containers.

        Returns:
            list[CheckResult]: One result per container, or one unknown result when Docker cannot be read.
        """
        try:
            containers = self.docker_client.project_containers(_COMPOSE_PROJECT)
        except (DockerError, FileNotFoundError, subprocess.TimeoutExpired) as error:
            return [
                self.result(
                    'docker',
                    _PLATFORM,
                    'Docker containers',
                    CheckStatus.UNKNOWN,
                    f'Docker could not be read: {error}',
                ),
            ]
        results = []
        for container in containers:
            details = {
                'state': container.state,
                'status': container.status,
            }
            if container.state != 'running':
                status = CheckStatus.FAILURE
                message = f'Not running: {container.status}.'
            elif container.is_unhealthy:
                status = CheckStatus.FAILURE
                message = f'Running but unhealthy: {container.status}.'
            else:
                status = CheckStatus.OK
                message = f'{container.status}.'
            label = container.name.removeprefix(f'{_COMPOSE_PROJECT}-')
            results.append(
                self.result(
                    f'container:{container.name}',
                    _PLATFORM,
                    f'Container {label}',
                    status,
                    message,
                    details=details,
                ),
            )
        return results

    def _timed(self, identifier: str, label: str, milliseconds: float) -> CheckResult:
        """Judges a successful probe by its response time.

        Args:
            identifier (str): The check identifier after the area.
            label (str): The human label.
            milliseconds (float): The probe's round trip.

        Returns:
            CheckResult: OK, or a warning when slower than the limit.
        """
        if milliseconds > self.thresholds.slow_warning_milliseconds:
            status = CheckStatus.WARNING
            message = f'Answered slowly, in {milliseconds:.0f} ms.'
        else:
            status = CheckStatus.OK
            message = f'Answered in {milliseconds:.1f} ms.'
        return self.result(
            identifier,
            _PLATFORM,
            label,
            status,
            message,
            value=milliseconds,
            details={
                'milliseconds': milliseconds,
            },
        )

    def _unreachable(self, identifier: str, label: str, error: Exception) -> CheckResult:
        """Builds the failure result for a probe that raised.

        Args:
            identifier (str): The check identifier after the area.
            label (str): The human label.
            error (Exception): The probe's exception.

        Returns:
            CheckResult: A failure naming the error.
        """
        return self.result(
            identifier,
            _PLATFORM,
            label,
            CheckStatus.FAILURE,
            f'Unreachable: {type(error).__name__}: {error}',
        )

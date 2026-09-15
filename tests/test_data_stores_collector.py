"""Tests for DataStoresCollector."""

import json

import httpx
import redis

from system_monitor.checks.check_result import CheckStatus
from system_monitor.collectors.data_stores_collector import DataStoresCollector
from system_monitor.configuration.thresholds import DataStoreThresholds
from system_monitor.sources.docker_client import DockerClient
from tests.fakes import FakeCommandRunner, FakeRedisReader, FixedClock


class _FakeProbe:
    """A probe that returns a prepared time or raises a prepared error."""

    def __init__(self, milliseconds: float = 2.0, error: Exception | None = None):
        """Creates the probe.

        Args:
            milliseconds (float): The time to return.
            error (Exception | None): The error to raise instead, or None.
        """
        self.milliseconds = milliseconds
        self.error = error

    def _answer(self) -> float:
        """Returns the prepared time or raises the prepared error.

        Returns:
            float: The prepared time.

        Raises:
            Exception: The prepared error, when set.
        """
        if self.error is not None:
            raise self.error
        return self.milliseconds

    def ping_milliseconds(self) -> float:
        """Answers like MongoConnection.ping_milliseconds.

        Returns:
            float: The prepared time.
        """
        return self._answer()

    def select_one_milliseconds(self) -> float:
        """Answers like PostgresProbe.select_one_milliseconds.

        Returns:
            float: The prepared time.
        """
        return self._answer()

    def greeting_milliseconds(self) -> float:
        """Answers like RestApiProbe.greeting_milliseconds.

        Returns:
            float: The prepared time.
        """
        return self._answer()


class TestDataStoresCollector:
    """Tests for DataStoresCollector."""

    def test_collect_reachability_speed_and_containers(self):
        """Checks an unreachable Redis, a slow REST API, a healthy store and an unhealthy container.

        Raises:
            AssertionError: A status is wrong.
        """
        reader = FakeRedisReader()
        reader.ping_error = redis.ConnectionError('refused')
        runner = FakeCommandRunner()
        lines = [
            json.dumps(
                {
                    'Names': 'unified_broker_interface-redis-1',
                    'State': 'running',
                    'Status': 'Up 4 days (unhealthy)',
                },
            ),
            json.dumps(
                {
                    'Names': 'unified_broker_interface-mongodb-1',
                    'State': 'running',
                    'Status': 'Up 4 days (healthy)',
                },
            ),
        ]
        runner.add_response(
            [
                'docker',
                'ps',
            ],
            '\n'.join(lines) + '\n',
        )
        collector = DataStoresCollector(
            reader,
            _FakeProbe(4.0),
            _FakeProbe(8.0),
            _FakeProbe(900.0),
            DockerClient(runner),
            DataStoreThresholds(
                slow_warning_milliseconds=250,
                timeout_seconds=3,
            ),
            FixedClock(0),
        )
        results = {}
        for result in collector.collect():
            results[result.check_id] = result
        assert results['data_stores:redis'].status == CheckStatus.FAILURE
        assert 'refused' in results['data_stores:redis'].message
        assert results['data_stores:mongodb'].status == CheckStatus.OK
        assert results['data_stores:rest_api'].status == CheckStatus.WARNING
        assert results['data_stores:container:unified_broker_interface-redis-1'].status == CheckStatus.FAILURE
        assert results['data_stores:container:unified_broker_interface-mongodb-1'].status == CheckStatus.OK

    def test_collect_rest_api_error_is_failure(self):
        """Checks that an HTTP error from the REST API is a failure.

        Raises:
            AssertionError: The status is wrong.
        """
        collector = DataStoresCollector(
            FakeRedisReader(),
            _FakeProbe(),
            _FakeProbe(),
            _FakeProbe(error=httpx.ConnectError('connection refused')),
            DockerClient(FakeCommandRunner()),
            DataStoreThresholds(
                slow_warning_milliseconds=250,
                timeout_seconds=3,
            ),
            FixedClock(0),
        )
        results = {}
        for result in collector.collect():
            results[result.check_id] = result
        assert results['data_stores:rest_api'].status == CheckStatus.FAILURE

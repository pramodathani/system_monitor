"""Checks that UBI's TimescaleDB answers queries.

Typical usage example:

  probe = PostgresProbe(configuration, timeout_seconds=3)
  milliseconds = probe.select_one_milliseconds()
"""

import contextlib
import math
import time

import psycopg2

from system_monitor.configuration.unified_broker_interface_configuration import (
    UnifiedBrokerInterfaceConfiguration,
)


class PostgresProbe:
    """Opens a short connection to TimescaleDB and runs SELECT 1."""

    def __init__(
        self,
        configuration: UnifiedBrokerInterfaceConfiguration,
        timeout_seconds: float,
    ):
        """Creates the probe.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long connecting may take.
        """
        self.configuration = configuration
        self.timeout_seconds = timeout_seconds

    def select_one_milliseconds(self) -> float:
        """Connects, runs SELECT 1 and disconnects, measuring the whole round trip.

        Returns:
            float: The time taken in milliseconds.

        Raises:
            psycopg2.Error: TimescaleDB could not be reached or queried.
        """
        started = time.perf_counter()
        connection = psycopg2.connect(
            host=self.configuration.postgres_host,
            port=self.configuration.postgres_port,
            dbname=self.configuration.postgres_database,
            user=self.configuration.postgres_username,
            password=self.configuration.postgres_password,
            connect_timeout=max(1, math.ceil(self.timeout_seconds)),
            application_name='system_monitor',
        )
        with contextlib.closing(connection), connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return (time.perf_counter() - started) * 1000

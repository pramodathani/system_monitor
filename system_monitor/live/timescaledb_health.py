"""TimescaleDB's own account of itself, from the statistics views PostgreSQL keeps.

This store holds the tick history and the price history, so it is by far the largest of the three and the one whose size is worth watching. PostgreSQL also answers the "last reboot" question directly, through `pg_postmaster_start_time`, which is the moment the server process began rather than the moment the container did.

The connection is opened for the reading and closed again, exactly as `PostgresProbe` does, so the live view never holds an idle connection against `max_connections`.

Typical usage example:

  health = TimescaledbHealth(configuration, timeout_seconds=3)
  reading = health.read()
"""

import contextlib
import math
from typing import Any

import psycopg2

from system_monitor.configuration.unified_broker_interface_configuration import (
    UnifiedBrokerInterfaceConfiguration,
)

_NAME = 'timescaledb'
_LABEL = 'TimescaleDB'

_SERVER_QUERY = """
    SELECT
        version(),
        extract(epoch FROM pg_postmaster_start_time()),
        pg_database_size(current_database()),
        current_setting('max_connections'),
        current_database()
"""

_ACTIVITY_QUERY = """
    SELECT
        count(*) FILTER (WHERE state = 'active'),
        count(*)
    FROM pg_stat_activity
    WHERE datname = current_database()
"""

_STATISTICS_QUERY = """
    SELECT
        xact_commit,
        xact_rollback,
        blks_read,
        blks_hit,
        deadlocks
    FROM pg_stat_database
    WHERE datname = current_database()
"""

_EXTENSION_QUERY = """
    SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'
"""


class TimescaledbHealth:
    """Opens a short connection to TimescaleDB and reads its health."""

    def __init__(
        self,
        configuration: UnifiedBrokerInterfaceConfiguration,
        timeout_seconds: float,
    ):
        """Creates the reader.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long connecting may take.
        """
        self.configuration = configuration
        self.timeout_seconds = timeout_seconds

    def read(self) -> dict[str, Any]:
        """Asks TimescaleDB how it is.

        Returns:
            dict[str, Any]: The keys "name", "label", "online", "error", "response_milliseconds", "version", "started_at" and "parameters". When TimescaleDB cannot be reached, "online" is false and "error" says why.
        """
        try:
            return self._read_connected()
        except psycopg2.Error as error:
            return {
                'name': _NAME,
                'label': _LABEL,
                'online': False,
                'error': f'{type(error).__name__}: {error}',
                'response_milliseconds': None,
                'version': None,
                'started_at': None,
                'parameters': [],
            }

    def _read_connected(self) -> dict[str, Any]:
        """Connects and runs the four statistics queries.

        Returns:
            dict[str, Any]: The reading, with "online" true.

        Raises:
            psycopg2.Error: TimescaleDB could not be reached or queried.
        """
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
            cursor.execute(_SERVER_QUERY)
            version, started_at, database_bytes, maximum_connections, database_name = cursor.fetchone()
            cursor.execute(_ACTIVITY_QUERY)
            active_connections, total_connections = cursor.fetchone()
            cursor.execute(_STATISTICS_QUERY)
            statistics = cursor.fetchone()
            cursor.execute(_EXTENSION_QUERY)
            extension = cursor.fetchone()
        return {
            'name': _NAME,
            'label': _LABEL,
            'online': True,
            'error': None,
            'response_milliseconds': None,
            'version': self._short_version(version),
            'started_at': float(started_at) if started_at is not None else None,
            'parameters': self._parameters(
                extension,
                database_name,
                database_bytes,
                maximum_connections,
                active_connections,
                total_connections,
                statistics,
            ),
        }

    def _short_version(self, version: str | None) -> str | None:
        """Keeps only the product and release from PostgreSQL's long version string.

        Args:
            version (str | None): The whole `version()` string.

        Returns:
            str | None: The first two words, such as "PostgreSQL 18.6", or None when there is no version.
        """
        if not version:
            return None
        words = version.split()
        return ' '.join(words[:2])

    def _parameters(
        self,
        extension: tuple[Any, ...] | None,
        database_name: str,
        database_bytes: int,
        maximum_connections: str,
        active_connections: int,
        total_connections: int,
        statistics: tuple[Any, ...] | None,
    ) -> list[dict[str, Any]]:
        """Chooses the readings worth showing from the query results.

        Args:
            extension (tuple[Any, ...] | None): The TimescaleDB extension version row, or None when it is not installed.
            database_name (str): The database being read.
            database_bytes (int): The database's size on disk.
            maximum_connections (str): The `max_connections` setting.
            active_connections (int): Connections currently running a query.
            total_connections (int): Connections open against the database.
            statistics (tuple[Any, ...] | None): The `pg_stat_database` row, or None when there is none.

        Returns:
            list[dict[str, Any]]: One entry per reading, each with "group", "name" and "value".
        """
        commits, rollbacks, blocks_read, blocks_hit, deadlocks = statistics or (
            None,
            None,
            None,
            None,
            None,
        )
        readings = [
            ('Database', 'Name', database_name),
            ('Database', 'Size in bytes', database_bytes),
            ('Database', 'TimescaleDB extension', extension[0] if extension else 'not installed'),
            ('Connections', 'Active', active_connections),
            ('Connections', 'Open', total_connections),
            ('Connections', 'Limit', maximum_connections),
            ('Work', 'Transactions committed', commits),
            ('Work', 'Transactions rolled back', rollbacks),
            ('Work', 'Blocks read from disk', blocks_read),
            ('Work', 'Blocks read from cache', blocks_hit),
            ('Work', 'Deadlocks', deadlocks),
        ]
        parameters = []
        for group, name, value in readings:
            parameters.append(
                {
                    'group': group,
                    'name': name,
                    'value': value,
                },
            )
        return parameters

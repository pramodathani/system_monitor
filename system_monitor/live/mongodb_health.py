"""MongoDB's own account of itself, from serverStatus and dbStats.

MongoDB holds the broker credentials and the login tokens, so it is small but not optional: a request that cannot read it cannot authenticate. The parameters chosen therefore lean on connections rather than on data volume, because running out of connections is the way this particular MongoDB fails.

Typical usage example:

  health = MongodbHealth(mongo_connection)
  reading = health.read()
"""

from typing import Any

import pymongo.errors

from system_monitor.sources.mongo_connection import MongoConnection

_NAME = 'mongodb'
_LABEL = 'MongoDB'


class MongodbHealth:
    """Reads MongoDB's serverStatus and dbStats and turns them into a health reading."""

    def __init__(self, mongo_connection: MongoConnection):
        """Creates the reader.

        Args:
            mongo_connection (MongoConnection): The connection to ask.
        """
        self.mongo_connection = mongo_connection

    def read(self) -> dict[str, Any]:
        """Asks MongoDB how it is.

        Returns:
            dict[str, Any]: The keys "name", "label", "online", "error", "response_milliseconds", "version", "uptime_seconds" and "parameters". When MongoDB cannot be reached, "online" is false and "error" says why.
        """
        try:
            milliseconds = self.mongo_connection.ping_milliseconds()
            database = self.mongo_connection.database()
            server_status = database.command('serverStatus')
            database_statistics = database.command('dbStats')
        except pymongo.errors.PyMongoError as error:
            return {
                'name': _NAME,
                'label': _LABEL,
                'online': False,
                'error': f'{type(error).__name__}: {error}',
                'response_milliseconds': None,
                'version': None,
                'uptime_seconds': None,
                'parameters': [],
            }
        return {
            'name': _NAME,
            'label': _LABEL,
            'online': True,
            'error': None,
            'response_milliseconds': milliseconds,
            'version': server_status.get('version'),
            'uptime_seconds': server_status.get('uptime'),
            'parameters': self._parameters(server_status, database_statistics),
        }

    def _parameters(
        self,
        server_status: dict[str, Any],
        database_statistics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Chooses the readings worth showing from the two replies.

        Args:
            server_status (dict[str, Any]): The serverStatus reply.
            database_statistics (dict[str, Any]): The dbStats reply.

        Returns:
            list[dict[str, Any]]: One entry per reading, each with "group", "name" and "value".
        """
        connections = server_status.get('connections') or {}
        network = server_status.get('network') or {}
        readings = [
            ('Connections', 'Current', connections.get('current')),
            ('Connections', 'Active', connections.get('active')),
            ('Connections', 'Available', connections.get('available')),
            ('Connections', 'Created since start', connections.get('totalCreated')),
            ('Connections', 'Rejected', connections.get('rejected')),
            ('Work', 'Requests served', network.get('numRequests')),
            ('Work', 'Bytes in', network.get('bytesIn')),
            ('Work', 'Bytes out', network.get('bytesOut')),
            ('Database', 'Name', database_statistics.get('db')),
            ('Database', 'Collections', database_statistics.get('collections')),
            ('Database', 'Documents', database_statistics.get('objects')),
            ('Database', 'Data size in bytes', database_statistics.get('dataSize')),
            ('Database', 'Storage size in bytes', database_statistics.get('storageSize')),
            ('Database', 'Indexes', database_statistics.get('indexes')),
            ('Database', 'Index size in bytes', database_statistics.get('indexSize')),
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

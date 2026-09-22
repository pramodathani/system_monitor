"""Redis's own account of itself: whether it answers, how long it has been up and how hard it is working.

Everything here comes from one INFO call plus a DBSIZE, so the whole reading costs two round trips. The parameters chosen are the ones that say whether Redis is in trouble rather than merely busy: memory against its limit, whether the last background save succeeded, how many clients are blocked, and whether any connection or key has been turned away.

Typical usage example:

  health = RedisHealth(redis_reader)
  reading = health.read()
"""

from typing import Any

import redis

from system_monitor.sources.redis_reader import RedisReader

_NAME = 'redis'
_LABEL = 'Redis'


class RedisHealth:
    """Reads Redis's INFO and turns it into a health reading."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): The connection to ask.
        """
        self.redis_reader = redis_reader

    def read(self) -> dict[str, Any]:
        """Asks Redis how it is.

        Returns:
            dict[str, Any]: The keys "name", "label", "online", "error", "response_milliseconds", "version", "uptime_seconds" and "parameters". When Redis cannot be reached, "online" is false and "error" says why.
        """
        try:
            milliseconds = self.redis_reader.ping_milliseconds()
            information = self.redis_reader.client.info()
            key_count = self.redis_reader.client.dbsize()
        except redis.RedisError as error:
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
            'version': information.get('redis_version'),
            'uptime_seconds': information.get('uptime_in_seconds'),
            'parameters': self._parameters(information, key_count),
        }

    def _parameters(self, information: dict[str, Any], key_count: int) -> list[dict[str, Any]]:
        """Chooses the readings worth showing from the INFO reply.

        Args:
            information (dict[str, Any]): The parsed INFO reply.
            key_count (int): How many keys the selected database holds.

        Returns:
            list[dict[str, Any]]: One entry per reading, each with "group", "name" and "value".
        """
        maximum_memory = information.get('maxmemory_human')
        if information.get('maxmemory') in (0, '0'):
            maximum_memory = 'no limit'
        readings = [
            ('Memory', 'Used', information.get('used_memory_human')),
            ('Memory', 'Peak used', information.get('used_memory_peak_human')),
            ('Memory', 'Limit', maximum_memory),
            ('Memory', 'Fragmentation ratio', information.get('mem_fragmentation_ratio')),
            ('Memory', 'Keys evicted', information.get('evicted_keys')),
            ('Clients', 'Connected', information.get('connected_clients')),
            ('Clients', 'Blocked', information.get('blocked_clients')),
            ('Clients', 'Rejected', information.get('rejected_connections')),
            ('Work', 'Keys in database', key_count),
            ('Work', 'Commands per second', information.get('instantaneous_ops_per_sec')),
            ('Work', 'Commands processed', information.get('total_commands_processed')),
            ('Work', 'Keyspace hits', information.get('keyspace_hits')),
            ('Work', 'Keyspace misses', information.get('keyspace_misses')),
            ('Persistence', 'Last background save', information.get('rdb_last_bgsave_status')),
            ('Persistence', 'Append-only file', 'on' if information.get('aof_enabled') else 'off'),
            ('Persistence', 'Last save', information.get('rdb_last_save_time')),
            ('Role', 'Replication role', information.get('role')),
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

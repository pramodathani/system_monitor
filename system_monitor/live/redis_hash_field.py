"""Reads one named field of a Redis hash whose value is a single JSON document.

The `last_login` hash is shaped this way: one field per broker plus `unified_broker_interface` for the application's own token, each holding the document a login wrote. It is read a field at a time rather than whole, so a page asking about one broker does not pull in every other broker's login.

Typical usage example:

  field = RedisHashField(redis_reader)
  answer = field.read('last_login', 'unified_broker_interface')
"""

import json
from typing import Any

from system_monitor.sources.redis_reader import RedisReader


class RedisHashField:
    """Reads a single hash field and parses it as JSON when it is JSON."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): Reads the hash.
        """
        self.redis_reader = redis_reader

    def read(self, key: str, field: str) -> dict[str, Any]:
        """Reads one field and describes what was found.

        Args:
            key (str): The hash key.
            field (str): The field name.

        Returns:
            dict[str, Any]: The keys "key", "field", "kind", "exists", "byte_size", "expires_in_seconds", "document" and "text".

        Raises:
            redis.RedisError: Redis could not be read.
        """
        text = self.redis_reader.client.hget(key, field)
        if text is None:
            return {
                'key': key,
                'field': field,
                'kind': 'none',
                'exists': False,
                'byte_size': 0,
                'expires_in_seconds': None,
                'document': None,
                'text': None,
            }
        answer = {
            'key': key,
            'field': field,
            'kind': 'hash_field',
            'exists': True,
            'byte_size': len(text.encode('utf-8')),
            'expires_in_seconds': None,
            'document': None,
            'text': None,
        }
        try:
            answer['document'] = json.loads(text)
        except ValueError:
            answer['text'] = text
        return answer

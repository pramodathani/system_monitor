"""Reads one Redis key whose value is a single JSON document.

The value is returned exactly as Redis holds it. Nothing is redacted, summarised or reordered, because the live view exists to show what is actually stored.

Typical usage example:

  document = RedisDocument(redis_reader)
  answer = document.read('zerodha:session:status')
"""

import json
from typing import Any

from system_monitor.sources.redis_reader import RedisReader


class RedisDocument:
    """Reads a Redis string key and parses it as JSON when it is JSON."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): Reads the key.
        """
        self.redis_reader = redis_reader

    def read(self, key: str) -> dict[str, Any]:
        """Reads one key and describes what was found.

        Args:
            key (str): The Redis key.

        Returns:
            dict[str, Any]: The keys "key", "kind", "exists", "byte_size", "expires_in_seconds", "document" and "text". "document" holds the parsed JSON, and "text" the raw value when it is not JSON.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        client = self.redis_reader.client
        kind = client.type(key)
        if kind == 'none':
            return self._absent(key)
        if kind != 'string':
            return self._wrong_kind(key, kind)
        text = client.get(key)
        if text is None:
            return self._absent(key)
        answer = {
            'key': key,
            'kind': 'string',
            'exists': True,
            'byte_size': len(text.encode('utf-8')),
            'expires_in_seconds': self._expires_in_seconds(key),
            'document': None,
            'text': None,
        }
        try:
            answer['document'] = json.loads(text)
        except ValueError:
            answer['text'] = text
        return answer

    def _absent(self, key: str) -> dict[str, Any]:
        """Describes a key that Redis does not hold.

        Args:
            key (str): The Redis key.

        Returns:
            dict[str, Any]: The answer with "exists" false.
        """
        return {
            'key': key,
            'kind': 'none',
            'exists': False,
            'byte_size': 0,
            'expires_in_seconds': None,
            'document': None,
            'text': None,
        }

    def _wrong_kind(self, key: str, kind: str) -> dict[str, Any]:
        """Describes a key that exists but is not a string.

        Args:
            key (str): The Redis key.
            kind (str): The type Redis reported, such as "hash".

        Returns:
            dict[str, Any]: The answer naming the type that was found.
        """
        return {
            'key': key,
            'kind': kind,
            'exists': True,
            'byte_size': 0,
            'expires_in_seconds': self._expires_in_seconds(key),
            'document': None,
            'text': None,
        }

    def _expires_in_seconds(self, key: str) -> int | None:
        """Reads how long a key has left to live.

        Args:
            key (str): The Redis key.

        Returns:
            int | None: The seconds remaining, or None when the key never expires.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        remaining = self.redis_reader.client.ttl(key)
        if remaining is None or remaining < 0:
            return None
        return int(remaining)

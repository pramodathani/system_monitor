"""Reads a Redis hash whose every field holds its own JSON document.

A broker's orders and positions are stored this way, one field per order or position, merged from the poller and the websocket. The hash is small enough to send whole, so every field is read and the companion key recording the last successful poll is read beside it.

Typical usage example:

  documents = RedisHashDocuments(redis_reader)
  answer = documents.read('zerodha:orders:orders')
"""

import json
from typing import Any

from system_monitor.sources.redis_reader import RedisReader

_POLLED_AT_SUFFIX = ':polled_at'


class RedisHashDocuments:
    """Reads every field of a hash of JSON documents."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): Reads the hash.
        """
        self.redis_reader = redis_reader

    def read(self, key: str) -> dict[str, Any]:
        """Reads every field of one hash.

        Args:
            key (str): The hash key.

        Returns:
            dict[str, Any]: The keys "key", "exists", "field_count", "expires_in_seconds", "polled_at" and "entries". Each entry has "field" and either "document" or "text".

        Raises:
            redis.RedisError: Redis could not be read.
        """
        client = self.redis_reader.client
        kind = client.type(key)
        if kind == 'none':
            return {
                'key': key,
                'exists': False,
                'field_count': 0,
                'expires_in_seconds': None,
                'polled_at': self._polled_at(key),
                'entries': [],
            }
        entries = []
        for field, value in self.redis_reader.scan_hash(key):
            entries.append(self._entry(field, value))
        entries.sort(key=self._sort_key)
        return {
            'key': key,
            'exists': True,
            'field_count': len(entries),
            'expires_in_seconds': self._expires_in_seconds(key),
            'polled_at': self._polled_at(key),
            'entries': entries,
        }

    def _entry(self, field: str, value: str) -> dict[str, Any]:
        """Builds one entry from a field and its stored value.

        Args:
            field (str): The hash field name.
            value (str): The stored text.

        Returns:
            dict[str, Any]: The keys "field", "document" and "text".
        """
        entry = {
            'field': field,
            'document': None,
            'text': None,
        }
        try:
            entry['document'] = json.loads(value)
        except ValueError:
            entry['text'] = value
        return entry

    def _sort_key(self, entry: dict[str, Any]) -> str:
        """Orders entries by their field name, so a page does not reshuffle between reads.

        Args:
            entry (dict[str, Any]): One entry.

        Returns:
            str: The field name.
        """
        return entry['field']

    def _polled_at(self, key: str) -> str | None:
        """Reads the companion key saying when the book was last read successfully.

        Args:
            key (str): The hash key.

        Returns:
            str | None: The stored epoch seconds as text, or None when there is no such key.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        return self.redis_reader.get_text(f'{key}{_POLLED_AT_SUFFIX}')

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

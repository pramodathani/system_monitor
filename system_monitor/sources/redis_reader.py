"""Read-only access to UBI's Redis.

The reader exposes only commands that read. Nothing in the monitor writes to UBI's Redis.

Typical usage example:

  reader = RedisReader.from_configuration(configuration, timeout_seconds=3)
  status = reader.get_json('zerodha:session:status')
"""

import json
import time
from collections.abc import Iterator
from typing import Any

import redis

from system_monitor.configuration.unified_broker_interface_configuration import (
    UnifiedBrokerInterfaceConfiguration,
)


class RedisReader:
    """Reads strings, hashes and streams from Redis."""

    def __init__(self, client: redis.Redis):
        """Wraps a Redis client that decodes responses to text.

        Args:
            client (redis.Redis): A client created with decode_responses=True.
        """
        self.client = client

    @classmethod
    def from_configuration(
        cls,
        configuration: UnifiedBrokerInterfaceConfiguration,
        timeout_seconds: float,
    ) -> RedisReader:
        """Creates a reader connected to UBI's Redis.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long a command may take before it fails.

        Returns:
            RedisReader: The reader. It connects on its first command.
        """
        client = redis.Redis(
            host=configuration.redis_host,
            port=configuration.redis_port,
            db=configuration.redis_database,
            username=configuration.redis_username,
            password=configuration.redis_password,
            decode_responses=True,
            socket_timeout=timeout_seconds,
            socket_connect_timeout=timeout_seconds,
        )
        return cls(client)

    def ping_milliseconds(self) -> float:
        """Measures how long Redis takes to answer a PING.

        Returns:
            float: The round trip in milliseconds.

        Raises:
            redis.RedisError: Redis could not be reached.
        """
        started = time.perf_counter()
        self.client.ping()
        return (time.perf_counter() - started) * 1000

    def get_text(self, key: str) -> str | None:
        """Reads a string key.

        Args:
            key (str): The key.

        Returns:
            str | None: The value, or None when the key does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        return self.client.get(key)

    def get_json(self, key: str) -> Any:
        """Reads a string key that holds a JSON document.

        Args:
            key (str): The key.

        Returns:
            Any: The parsed document, or None when the key does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The value is not valid JSON.
        """
        text = self.get_text(key)
        if text is None:
            return None
        return self._parse_json(key, text)

    def hash_get_json(self, key: str, field: str) -> Any:
        """Reads one field of a hash that holds a JSON document.

        Args:
            key (str): The hash key.
            field (str): The field.

        Returns:
            Any: The parsed document, or None when the key or field does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The value is not valid JSON.
        """
        text = self.client.hget(key, field)
        if text is None:
            return None
        return self._parse_json(f'{key} {field}', text)

    def hash_length(self, key: str) -> int:
        """Counts the fields of a hash.

        Args:
            key (str): The hash key.

        Returns:
            int: The number of fields, which is 0 when the key does not exist.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        return self.client.hlen(key)

    def scan_hash(self, key: str, batch_size: int = 500) -> Iterator[tuple[str, str]]:
        """Walks every field of a hash in batches, without blocking Redis.

        Args:
            key (str): The hash key.
            batch_size (int): How many fields to ask for per round trip.

        Yields:
            tuple[str, str]: The next field name and its value.

        Raises:
            redis.RedisError: Redis could not be read.
        """
        yield from self.client.hscan_iter(key, count=batch_size)

    def stream_info(self, key: str) -> dict[str, Any] | None:
        """Reads a stream's length, last ID and entries-added counter.

        Args:
            key (str): The stream key.

        Returns:
            dict[str, Any] | None: The XINFO STREAM reply without its first and last entries, or None when the stream does not exist.

        Raises:
            redis.RedisError: Redis could not be read, or the key is not a stream.
        """
        try:
            info = self.client.xinfo_stream(key)
        except redis.ResponseError as error:
            if 'no such key' in str(error).lower():
                return None
            raise
        info.pop('first-entry', None)
        info.pop('last-entry', None)
        return info

    def stream_groups(self, key: str) -> list[dict[str, Any]]:
        """Reads the consumer groups of a stream.

        Args:
            key (str): The stream key.

        Returns:
            list[dict[str, Any]]: One XINFO GROUPS entry per group, with name, consumers, pending, lag and last-delivered-id.

        Raises:
            redis.RedisError: Redis could not be read, or the stream does not exist.
        """
        return self.client.xinfo_groups(key)

    def _parse_json(self, where: str, text: str) -> Any:
        """Parses a JSON value read from Redis.

        Args:
            where (str): The key, and field if any, for the error message.
            text (str): The stored text.

        Returns:
            Any: The parsed document.

        Raises:
            ValueError: The text is not valid JSON.
        """
        try:
            return json.loads(text)
        except ValueError as error:
            raise ValueError(f'Redis value is not JSON: {where}') from error

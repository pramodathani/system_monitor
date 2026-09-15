"""Read-only access to UBI's MongoDB.

Typical usage example:

  connection = MongoConnection(configuration, timeout_seconds=3)
  documents = connection.exchange_calendars()
"""

import threading
import time
from typing import Any

import pymongo
import pymongo.database

from system_monitor.configuration.unified_broker_interface_configuration import (
    UnifiedBrokerInterfaceConfiguration,
)


class MongoConnection:
    """A lazily opened MongoDB client for UBI's database."""

    def __init__(
        self,
        configuration: UnifiedBrokerInterfaceConfiguration,
        timeout_seconds: float,
    ):
        """Creates the connection without opening it.

        Args:
            configuration (UnifiedBrokerInterfaceConfiguration): UBI's store addresses and credentials.
            timeout_seconds (float): How long server selection and connecting may take.
        """
        self.configuration = configuration
        self.timeout_seconds = timeout_seconds
        self._client = None
        self._lock = threading.Lock()

    def database(self) -> pymongo.database.Database:
        """Opens the client if needed and returns UBI's database.

        Returns:
            pymongo.database.Database: UBI's database.
        """
        with self._lock:
            if self._client is None:
                timeout_milliseconds = int(self.timeout_seconds * 1000)
                self._client = pymongo.MongoClient(
                    host=self.configuration.mongodb_host,
                    port=self.configuration.mongodb_port,
                    username=self.configuration.mongodb_username,
                    password=self.configuration.mongodb_password,
                    serverSelectionTimeoutMS=timeout_milliseconds,
                    connectTimeoutMS=timeout_milliseconds,
                    socketTimeoutMS=timeout_milliseconds,
                )
            return self._client[self.configuration.mongodb_database]

    def ping_milliseconds(self) -> float:
        """Measures how long MongoDB takes to answer a ping.

        Returns:
            float: The round trip in milliseconds.

        Raises:
            pymongo.errors.PyMongoError: MongoDB could not be reached.
        """
        database = self.database()
        started = time.perf_counter()
        database.command('ping')
        return (time.perf_counter() - started) * 1000

    def exchange_calendars(self) -> list[dict[str, Any]]:
        """Reads each exchange's trading hours, holidays and special sessions.

        Returns:
            list[dict[str, Any]]: One document per exchange with the keys exchange, trading_hours, holidays and special_sessions.

        Raises:
            pymongo.errors.PyMongoError: MongoDB could not be read.
        """
        projection = {
            '_id': 0,
            'exchange': 1,
            'trading_hours': 1,
            'holidays': 1,
            'special_sessions': 1,
        }
        return list(self.database()['exchange_details'].find({}, projection))

    def close(self) -> None:
        """Closes the client if it was opened."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

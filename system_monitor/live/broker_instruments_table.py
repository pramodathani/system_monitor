"""One broker's own instrument master, as that broker's morning download left it in Redis.

The hash is keyed by the broker's own key for an instrument, such as Zerodha's `instrument_token`, and each value is that row of the broker's instrument file as a JSON array. The column names are in the broker's meta document, which is why they are read from there rather than assumed.

Typical usage example:

  table = BrokerInstrumentsTable(redis_reader, 'zerodha')
  page = table.page(cursor='0', limit=100)
"""

from system_monitor.live.row_table import RowTable
from system_monitor.sources.redis_reader import RedisReader


class BrokerInstrumentsTable(RowTable):
    """The hash `<broker>:instruments:master`."""

    def __init__(self, redis_reader: RedisReader, broker: str):
        """Creates the table reader for one broker.

        Args:
            redis_reader (RedisReader): Reads the hash and the meta document.
            broker (str): The broker name, such as "zerodha".
        """
        super().__init__(
            redis_reader,
            f'{broker}:instruments:master',
            'broker_key',
        )
        self.broker = broker
        self.meta_key = f'{broker}:instruments:meta'

    def columns(self) -> list[str]:
        """Names the columns of the broker's instrument file, from its meta document.

        Returns:
            list[str]: The column names, which is empty when the meta document is missing or names none.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        meta = self.redis_reader.get_json(self.meta_key)
        if not isinstance(meta, dict):
            return []
        columns = meta.get('columns')
        if not isinstance(columns, list):
            return []
        return [str(column) for column in columns]

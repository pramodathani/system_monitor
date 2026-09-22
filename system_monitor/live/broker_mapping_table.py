"""What one broker calls each instrument that the mapping run recognised.

Every broker's mappings share the single hash `unified:broker_mappings`, whose field is `broker:instrument_id`, so reading one broker's table means keeping only the fields that begin with that broker's name. The broker's name is then removed from the key shown, leaving the instrument id the row is really about.

The hash holds close to two million fields across all ten brokers. Its length is reported as it stands, because counting one broker's share would mean walking the whole hash before the first row could be shown.

Typical usage example:

  table = BrokerMappingTable(redis_reader, 'zerodha')
  page = table.page(cursor='0', limit=100)
"""

from system_monitor.live.mapping_meta import MappingMeta
from system_monitor.live.row_table import RowTable
from system_monitor.sources.redis_reader import RedisReader


class BrokerMappingTable(RowTable):
    """One broker's slice of the hash `unified:broker_mappings`."""

    def __init__(self, redis_reader: RedisReader, broker: str):
        """Creates the table reader for one broker.

        Args:
            redis_reader (RedisReader): Reads the hash and the mapping meta document.
            broker (str): The broker name, such as "zerodha".
        """
        super().__init__(
            redis_reader,
            'unified:broker_mappings',
            'instrument_id',
            field_prefix=f'{broker}:',
        )
        self.broker = broker
        self.mapping_meta = MappingMeta(redis_reader)

    def columns(self) -> list[str]:
        """Names the mapping columns from the mapping meta document.

        Returns:
            list[str]: The column names, which is empty when the meta document is missing or names none.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        return self.mapping_meta.columns('broker_mappings')

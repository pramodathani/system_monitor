"""Every instrument the morning's mapping run recognised, keyed by its unified instrument id.

This is the one table that is the same for all ten brokers: a broker's token has already been resolved to an instrument, so a row here describes the contract itself rather than any broker's name for it. Its column names come from `unified:mapping:meta`, under `columns.instruments`.

Typical usage example:

  table = UnifiedInstrumentsTable(redis_reader)
  page = table.page(cursor='0', limit=100)
"""

from system_monitor.live.mapping_meta import MappingMeta
from system_monitor.live.row_table import RowTable
from system_monitor.sources.redis_reader import RedisReader


class UnifiedInstrumentsTable(RowTable):
    """The hash `unified:instruments`."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the table reader.

        Args:
            redis_reader (RedisReader): Reads the hash and the mapping meta document.
        """
        super().__init__(
            redis_reader,
            'unified:instruments',
            'instrument_id',
        )
        self.mapping_meta = MappingMeta(redis_reader)

    def columns(self) -> list[str]:
        """Names the instrument columns from the mapping meta document.

        Returns:
            list[str]: The column names, which is empty when the meta document is missing or names none.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        return self.mapping_meta.columns('instruments')

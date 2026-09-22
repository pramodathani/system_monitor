"""The mapping run's own record of what it produced this morning.

Two of the live view's tables store their rows as bare JSON arrays with no field names, and both take their column names from this one document. The date it carries is also what the page shows to say which day's mapping is on screen.

Typical usage example:

  meta = MappingMeta(redis_reader)
  columns = meta.columns('instruments')
"""

from typing import Any

from system_monitor.sources.redis_reader import RedisReader

_KEY = 'unified:mapping:meta'


class MappingMeta:
    """The document `unified:mapping:meta`."""

    def __init__(self, redis_reader: RedisReader):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): Reads the document.
        """
        self.redis_reader = redis_reader

    def document(self) -> dict[str, Any]:
        """Reads the whole meta document.

        Returns:
            dict[str, Any]: The document, which is empty when the key is missing or is not an object.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The document is not JSON.
        """
        meta = self.redis_reader.get_json(_KEY)
        if not isinstance(meta, dict):
            return {}
        return meta

    def columns(self, table: str) -> list[str]:
        """Names the columns of one of the mapped tables.

        Args:
            table (str): The table's name inside the document's "columns" object, either "instruments" or "broker_mappings".

        Returns:
            list[str]: The column names, which is empty when the document does not name them.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The document is not JSON.
        """
        columns = self.document().get('columns')
        if not isinstance(columns, dict):
            return []
        named = columns.get(table)
        if not isinstance(named, list):
            return []
        return [str(column) for column in named]

    def mapping_date(self) -> str | None:
        """The date the stored mapping was produced for.

        Returns:
            str | None: The date as YYYY-MM-DD, or None when the document does not carry one.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The document is not JSON.
        """
        stored = self.document().get('mapping_date')
        if stored is None:
            return None
        return str(stored)

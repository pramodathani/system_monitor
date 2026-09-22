"""The common mechanism behind the three big instrument tables in Redis.

Each of those tables is one Redis hash holding hundreds of thousands of fields, where the field is the row's key and the value is that row's cells as a JSON array in a fixed column order. The column names live once in a separate meta document rather than in every row.

A hash that large cannot be sent to a browser whole, so it is read in two ways. Paging walks the hash with HSCAN and hands the cursor back to the caller, which is cheap because HSCAN returns a slice without loading the rest. Searching walks the whole hash once and keeps the rows that match, which costs a few seconds on the largest table and so is only ever done when the reader asked for it.

Subclasses say which key they read, what the field means and where the column names come from.

Typical usage example:

  table = UnifiedInstrumentsTable(redis_reader)
  page = table.page(cursor='0', limit=100)
"""

import json
from typing import Any

from system_monitor.sources.redis_reader import RedisReader

_SMALLEST_SCAN_BATCH = 64
_SEARCH_BATCH = 5000


class RowTable:
    """A Redis hash of JSON array rows, read a page or a search at a time."""

    def __init__(
        self,
        redis_reader: RedisReader,
        key: str,
        key_column: str,
        field_prefix: str | None = None,
    ):
        """Creates the table reader.

        Args:
            redis_reader (RedisReader): Reads the hash and its meta document.
            key (str): The Redis hash holding the rows.
            key_column (str): What the hash field means, such as "instrument_id".
            field_prefix (str | None): Only fields beginning with this text are read, and the text is removed from the key shown. None reads every field.
        """
        self.redis_reader = redis_reader
        self.key = key
        self.key_column = key_column
        self.field_prefix = field_prefix

    def columns(self) -> list[str]:
        """Names the columns each row's values are in, in order.

        Returns:
            list[str]: The column names, which is empty when the meta document is missing.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        raise NotImplementedError

    def page(self, cursor: str, limit: int) -> dict[str, Any]:
        """Reads one page of rows, continuing from a cursor.

        A page can come back a little longer than asked for. HSCAN returns whole batches, and a batch cannot be trimmed without losing the rows the cursor has already moved past, so the last batch is kept entire. The batch size follows the limit rather than being fixed, which keeps the overshoot to a fraction of a page instead of hundreds of rows.

        Args:
            cursor (str): The cursor to continue from. "0" starts at the beginning.
            limit (int): How many rows to gather before returning.

        Returns:
            dict[str, Any]: The page, described by `_answer`.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The cursor is not a number, or the meta document is not JSON.
        """
        try:
            position = int(cursor)
        except ValueError as error:
            raise ValueError(f'Not a cursor: {cursor!r}') from error
        client = self.redis_reader.client
        rows = []
        scanned = 0
        batch_size = max(_SMALLEST_SCAN_BATCH, limit)
        while True:
            position, batch = client.hscan(
                self.key,
                cursor=position,
                count=batch_size,
                match=self._match(),
            )
            scanned += len(batch)
            for field, value in batch.items():
                rows.append(self._row(field, value))
            if position == 0 or len(rows) >= limit:
                break
        rows.sort(key=self._sort_key)
        next_cursor = None
        if position != 0:
            next_cursor = str(position)
        return self._answer(rows, next_cursor, scanned, None, True)

    def search(self, text: str, limit: int) -> dict[str, Any]:
        """Walks the whole hash and keeps the rows that contain some text.

        The text is matched without regard to case against the row's key and against every one of its cells.

        The answer is complete only when the walk reached the end of the hash and every match it found fits within the limit. A walk that finished but found more matches than were asked for is incomplete in the sense that matters to a reader, because rows were left out, so it is reported that way.

        Args:
            text (str): What to look for.
            limit (int): How many matching rows to gather before giving up the walk.

        Returns:
            dict[str, Any]: The matches, described by `_answer`.

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        wanted = text.strip().lower()
        client = self.redis_reader.client
        position = 0
        rows = []
        scanned = 0
        while True:
            position, batch = client.hscan(
                self.key,
                cursor=position,
                count=_SEARCH_BATCH,
                match=self._match(),
            )
            scanned += len(batch)
            for field, value in batch.items():
                if wanted not in f'{field} {value}'.lower():
                    continue
                rows.append(self._row(field, value))
            if len(rows) >= limit or position == 0:
                break
        complete = position == 0 and len(rows) <= limit
        rows.sort(key=self._sort_key)
        return self._answer(rows[:limit], None, scanned, text, complete)

    def _match(self) -> str | None:
        """The HSCAN pattern that keeps the walk to this table's own fields.

        Returns:
            str | None: The pattern, or None when every field belongs to the table.
        """
        if self.field_prefix is None:
            return None
        return f'{self.field_prefix}*'

    def _row(self, field: str, value: str) -> dict[str, Any]:
        """Turns one hash field and its value into a row.

        Args:
            field (str): The hash field, which is the row's key.
            value (str): The stored JSON array of cells.

        Returns:
            dict[str, Any]: The keys "key" and "values", where "values" is the raw text when the value is not a JSON array.
        """
        shown = field
        if self.field_prefix is not None:
            shown = field.removeprefix(self.field_prefix)
        try:
            values = json.loads(value)
        except ValueError:
            values = [
                value,
            ]
        if not isinstance(values, list):
            values = [
                values,
            ]
        return {
            'key': shown,
            'values': values,
        }

    def _sort_key(self, row: dict[str, Any]) -> str:
        """Orders rows by their key, so a page reads the same way twice.

        Args:
            row (dict[str, Any]): One row.

        Returns:
            str: The row's key.
        """
        return row['key']

    def _answer(
        self,
        rows: list[dict[str, Any]],
        cursor: str | None,
        scanned: int,
        search: str | None,
        complete: bool,
    ) -> dict[str, Any]:
        """Assembles the answer a page or a search returns.

        Args:
            rows (list[dict[str, Any]]): The rows gathered.
            cursor (str | None): The cursor the next page continues from, or None at the end of the hash.
            scanned (int): How many fields the walk looked at.
            search (str | None): The text searched for, or None for a plain page.
            complete (bool): Whether the walk finished rather than stopping at the row limit.

        Returns:
            dict[str, Any]: The keys "key", "exists", "key_column", "columns", "field_prefix", "total_fields", "rows", "cursor", "scanned_fields", "search" and "complete".

        Raises:
            redis.RedisError: Redis could not be read.
            ValueError: The meta document is not JSON.
        """
        total_fields = self.redis_reader.hash_length(self.key)
        return {
            'key': self.key,
            'exists': total_fields > 0,
            'key_column': self.key_column,
            'columns': self.columns(),
            'field_prefix': self.field_prefix,
            'total_fields': total_fields,
            'rows': rows,
            'cursor': cursor,
            'scanned_fields': scanned,
            'search': search,
            'complete': complete,
        }

"""The one object the live view's routes talk to.

It turns a tab name and a chosen broker into the right read: a string key, a hash field, a whole hash of documents, or a page of one of the three huge row tables. The routes stay thin as a result, and the rule that the browser names a tab rather than a key is enforced in exactly one place.

Typical usage example:

  reader = LiveViewReader(redis_reader, view_catalogue, inventory)
  answer = reader.read_view('broker', 'session_status', 'zerodha')
"""

from typing import Any

from system_monitor.live.broker_instruments_table import BrokerInstrumentsTable
from system_monitor.live.broker_mapping_table import BrokerMappingTable
from system_monitor.live.mapping_meta import MappingMeta
from system_monitor.live.redis_document import RedisDocument
from system_monitor.live.redis_hash_documents import RedisHashDocuments
from system_monitor.live.redis_hash_field import RedisHashField
from system_monitor.live.row_table import RowTable
from system_monitor.live.unified_instruments_table import UnifiedInstrumentsTable
from system_monitor.live.view_catalogue import ViewCatalogue
from system_monitor.sources.redis_reader import RedisReader
from system_monitor.sources.unit_inventory import UnitInventory

_MAXIMUM_PAGE_ROWS = 500
_MAXIMUM_SEARCH_ROWS = 500


class UnknownViewError(Exception):
    """A tab that the catalogue does not hold was asked for."""


class LiveViewReader:
    """Reads whichever Redis value one live view tab shows."""

    def __init__(
        self,
        redis_reader: RedisReader,
        view_catalogue: ViewCatalogue,
        inventory: UnitInventory,
    ):
        """Creates the reader.

        Args:
            redis_reader (RedisReader): Reads every key.
            view_catalogue (ViewCatalogue): The tabs that may be read.
            inventory (UnitInventory): Supplies the broker names the dropdowns offer.
        """
        self.redis_reader = redis_reader
        self.view_catalogue = view_catalogue
        self.inventory = inventory
        self.document = RedisDocument(redis_reader)
        self.hash_field = RedisHashField(redis_reader)
        self.hash_documents = RedisHashDocuments(redis_reader)
        self.mapping_meta = MappingMeta(redis_reader)

    def brokers(self) -> list[str]:
        """Lists the brokers the dropdowns offer.

        Returns:
            list[str]: The broker names, in the inventory's order.
        """
        return self.inventory.brokers()

    def read_view(
        self,
        scope: str,
        name: str,
        broker: str | None,
    ) -> dict[str, Any]:
        """Reads one tab that shows a document rather than a table.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name.
            broker (str | None): The broker chosen, or None for a tab that needs none.

        Returns:
            dict[str, Any]: The keys "scope", "name", "label", "kind", "note", "broker" and "value", where "value" is what the tab's reader returned.

        Raises:
            UnknownViewError: No tab has that name in that scope, or the tab is a table.
            ValueError: The tab needs a broker and none was given, or a stored value is not JSON.
            redis.RedisError: Redis could not be read.
        """
        view = self._require(scope, name)
        if view['kind'] == 'table':
            raise UnknownViewError(f'The {view["label"]} tab is a table; read it as a table.')
        broker = self._require_broker(view, broker)
        key = self.view_catalogue.key_for(view, broker)
        if view['kind'] == 'hash_field':
            field = view['field'].format(broker=broker) if broker else view['field']
            value = self.hash_field.read(key, field)
        elif view['kind'] == 'hash_documents':
            value = self.hash_documents.read(key)
        else:
            value = self.document.read(key)
        return {
            'scope': scope,
            'name': view['name'],
            'label': view['label'],
            'kind': view['kind'],
            'note': view['note'],
            'broker': broker,
            'value': value,
        }

    def read_table(
        self,
        scope: str,
        name: str,
        broker: str | None,
        cursor: str,
        limit: int,
        search: str | None,
    ) -> dict[str, Any]:
        """Reads one page of a tab that shows a table, or searches the whole table.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name.
            broker (str | None): The broker chosen, or None for a table that needs none.
            cursor (str): The cursor to continue from. "0" starts at the beginning.
            limit (int): How many rows to gather, at most 500.
            search (str | None): Text to look for in every row, or None to page through instead.

        Returns:
            dict[str, Any]: The keys "scope", "name", "label", "kind", "note", "broker" and "value", where "value" is the page the table returned.

        Raises:
            UnknownViewError: No tab has that name in that scope, or the tab is not a table.
            ValueError: The tab needs a broker and none was given, the cursor is not a number, or a stored value is not JSON.
            redis.RedisError: Redis could not be read.
        """
        view = self._require(scope, name)
        if view['kind'] != 'table':
            raise UnknownViewError(f'The {view["label"]} tab is not a table.')
        broker = self._require_broker(view, broker)
        table = self._table(scope, view, broker)
        if search is not None and search.strip() != '':
            rows = min(max(1, limit), _MAXIMUM_SEARCH_ROWS)
            value = table.search(search, rows)
        else:
            rows = min(max(1, limit), _MAXIMUM_PAGE_ROWS)
            value = table.page(cursor, rows)
        return {
            'scope': scope,
            'name': view['name'],
            'label': view['label'],
            'kind': view['kind'],
            'note': view['note'],
            'broker': broker,
            'value': value,
        }

    def _table(
        self,
        scope: str,
        view: dict[str, Any],
        broker: str | None,
    ) -> RowTable:
        """Chooses the table reader one table tab uses.

        Args:
            scope (str): Either "broker" or "unified".
            view (dict[str, Any]): The tab.
            broker (str | None): The broker chosen.

        Returns:
            RowTable: The reader for that table.

        Raises:
            UnknownViewError: The tab is a table the reader does not know how to build.
        """
        if scope == 'broker' and view['name'] == 'instruments_master':
            return BrokerInstrumentsTable(self.redis_reader, broker)
        if scope == 'unified' and view['name'] == 'instruments_master':
            return UnifiedInstrumentsTable(self.redis_reader)
        if scope == 'unified' and view['name'] == 'instruments_mapping':
            return BrokerMappingTable(self.redis_reader, broker)
        raise UnknownViewError(f'No table reader for {scope}/{view["name"]}.')

    def _require(self, scope: str, name: str) -> dict[str, Any]:
        """Finds a tab, refusing one the catalogue does not hold.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name.

        Returns:
            dict[str, Any]: The tab.

        Raises:
            UnknownViewError: No tab has that name in that scope.
        """
        view = self.view_catalogue.find(scope, name)
        if view is None:
            raise UnknownViewError(f'Not a live view tab: {scope}/{name}')
        return view

    def _require_broker(self, view: dict[str, Any], broker: str | None) -> str | None:
        """Checks the chosen broker against the tab's needs and the inventory.

        Args:
            view (dict[str, Any]): The tab.
            broker (str | None): The broker chosen.

        Returns:
            str | None: The broker to read with, or None for a tab that needs none.

        Raises:
            ValueError: The tab needs a broker and none was given, or the name is not one of UBI's brokers.
        """
        if not view['needs_broker']:
            return None
        if not broker:
            raise ValueError(f'The {view["label"]} tab needs a broker.')
        if broker not in self.brokers():
            raise ValueError(f'Not a unified_broker_interface broker: {broker}')
        return broker

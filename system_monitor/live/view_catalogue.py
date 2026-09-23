"""Every tab the live view offers, and the Redis key behind each one.

The browser asks for a tab by name and never by key. That is deliberate: a route that accepted a key would let anyone logged in read any key in UBI's Redis, including keys the monitor has no business showing, and would turn a reading page into a general Redis console. Declaring the tabs here keeps the set of readable keys fixed and reviewable in one place.

Each tab says how it should be read. A `document` is one string key holding a JSON document. A `hash_field` is one named field of a hash. A `hash_documents` is a hash with a JSON document in every field, small enough to send whole. A `table` is one of the three huge hashes of JSON array rows, which is paged and searched instead.

Two tabs are worth explaining. The unified session status reads `unified:session:status`, which `bin/unified/session/connect` writes and which is simply absent on a system where that script has not run; the application token the REST API actually authenticates with lives in the `last_login` hash instead, so it gets a tab of its own beside it. The broker mapping tab is a table because every broker's mappings share one hash of nearly two million fields.

Typical usage example:

  catalogue = ViewCatalogue()
  view = catalogue.find('broker', 'session_status')
"""

from typing import Any

_DOCUMENT = 'document'
_HASH_FIELD = 'hash_field'
_HASH_DOCUMENTS = 'hash_documents'
_TABLE = 'table'

_BROKER_SCOPE = 'broker'
_UNIFIED_SCOPE = 'unified'


class ViewCatalogue:
    """The fixed list of live view tabs, per scope."""

    def __init__(self):
        """Builds the catalogue."""
        self._views = {
            _BROKER_SCOPE: self._broker_views(),
            _UNIFIED_SCOPE: self._unified_views(),
        }

    def scopes(self) -> list[str]:
        """Names the two groups of tabs.

        Returns:
            list[str]: "broker" and "unified".
        """
        return [
            _BROKER_SCOPE,
            _UNIFIED_SCOPE,
        ]

    def views(self, scope: str) -> list[dict[str, Any]]:
        """Lists one scope's tabs, in the order the page shows them.

        Args:
            scope (str): Either "broker" or "unified".

        Returns:
            list[dict[str, Any]]: One entry per tab, each with "name", "label", "kind", "note" and "needs_broker".
        """
        listed = []
        for view in self._views.get(scope, []):
            listed.append(
                {
                    'name': view['name'],
                    'label': view['label'],
                    'kind': view['kind'],
                    'note': view['note'],
                    'needs_broker': view['needs_broker'],
                },
            )
        return listed

    def find(self, scope: str, name: str) -> dict[str, Any] | None:
        """Looks one tab up by its scope and name.

        Args:
            scope (str): Either "broker" or "unified".
            name (str): The tab's name, such as "session_status".

        Returns:
            dict[str, Any] | None: The tab, or None when no tab has that name in that scope.
        """
        for view in self._views.get(scope, []):
            if view['name'] == name:
                return view
        return None

    def key_for(self, view: dict[str, Any], broker: str | None) -> str:
        """Builds the Redis key one tab reads.

        Args:
            view (dict[str, Any]): The tab, as `find` returned it.
            broker (str | None): The broker chosen, or None for a tab that needs none.

        Returns:
            str: The Redis key.

        Raises:
            ValueError: The tab needs a broker and none was given.
        """
        template = view['key']
        if '{broker}' not in template:
            return template
        if not broker:
            raise ValueError(f'The {view["label"]} tab needs a broker.')
        return template.format(broker=broker)

    def _broker_views(self) -> list[dict[str, Any]]:
        """Writes out the tabs shown for one chosen broker.

        Returns:
            list[dict[str, Any]]: The broker tabs.
        """
        return [
            self._view(
                'session_status',
                'Session status',
                _DOCUMENT,
                '{broker}:session:status',
                'The broker\'s login status and the token in force, replaced on every login or logout.',
            ),
            self._view(
                'user_details',
                'User profile',
                _DOCUMENT,
                '{broker}:user:details',
                'The broker\'s own profile of the account, polled every minute.',
            ),
            self._view(
                'instruments_master',
                'Instruments master',
                _TABLE,
                '{broker}:instruments:master',
                'Every row of the broker\'s own instrument file, as this morning\'s download left it.',
            ),
            self._view(
                'instruments_meta',
                'Instruments meta',
                _DOCUMENT,
                '{broker}:instruments:meta',
                'What the download produced: its date, its row count and the column names the master rows are in.',
            ),
            self._view(
                'orders',
                'Orders',
                _HASH_DOCUMENTS,
                '{broker}:orders:orders',
                'Today\'s order book, one entry per order, merged from the poller and the websocket.',
            ),
            self._view(
                'trades',
                'Trades',
                _DOCUMENT,
                '{broker}:orders:trades',
                'Today\'s trade book as the broker last returned it.',
            ),
            self._view(
                'holdings',
                'Holdings',
                _DOCUMENT,
                '{broker}:portfolio:holdings',
                'The broker\'s holdings, polled every minute.',
            ),
            self._view(
                'positions',
                'Positions',
                _HASH_DOCUMENTS,
                '{broker}:portfolio:positions',
                'Today\'s positions, one entry per position, net and day as the broker holds them.',
            ),
            self._view(
                'funds',
                'Funds',
                _DOCUMENT,
                '{broker}:portfolio:funds',
                'The broker\'s funds and margins.',
            ),
            self._view(
                'stored_login',
                'Stored login',
                _HASH_FIELD,
                'last_login',
                'The login document in the shared `last_login` hash, which every process reads the token in force from.',
                field='{broker}',
            ),
        ]

    def _unified_views(self) -> list[dict[str, Any]]:
        """Writes out the tabs shown for the unified layer.

        Returns:
            list[dict[str, Any]]: The unified tabs.
        """
        return [
            self._view(
                'session_status',
                'Session status',
                _DOCUMENT,
                'unified:session:status',
                'The application\'s own session, written by `bin/unified/session/connect`. It is absent when that script has never run.',
                needs_broker=False,
            ),
            self._view(
                'application_token',
                'Application token',
                _HASH_FIELD,
                'last_login',
                'The application token the REST API actually authenticates with, in the shared `last_login` hash.',
                needs_broker=False,
                field='unified_broker_interface',
            ),
            self._view(
                'user_details',
                'User profile',
                _DOCUMENT,
                'unified:user:details',
                'Each broker\'s profile of the account, gathered into one document every minute.',
                needs_broker=False,
            ),
            self._view(
                'details_users',
                'User details',
                _DOCUMENT,
                'unified:details:users',
                'The MongoDB `user_details` collection, copied into Redis every minute.',
                needs_broker=False,
            ),
            self._view(
                'details_brokers',
                'Broker details',
                _DOCUMENT,
                'unified:details:brokers',
                'The MongoDB `broker_details` collection.',
                needs_broker=False,
            ),
            self._view(
                'details_exchanges',
                'Exchange details',
                _DOCUMENT,
                'unified:details:exchanges',
                'The MongoDB `exchange_details` collection, including trading hours and holidays.',
                needs_broker=False,
            ),
            self._view(
                'instruments_master',
                'Instruments master',
                _TABLE,
                'unified:instruments',
                'Every instrument this morning\'s mapping recognised, keyed by its unified instrument id.',
                needs_broker=False,
            ),
            self._view(
                'instruments_mapping',
                'Instruments mapping',
                _TABLE,
                'unified:broker_mappings',
                'What one broker calls each mapped instrument. Every broker shares one hash, so a broker must be chosen.',
            ),
            self._view(
                'orders',
                'Orders',
                _DOCUMENT,
                'unified:orders:orders',
                'Today\'s orders at every broker, combined every half second.',
                needs_broker=False,
            ),
            self._view(
                'trades',
                'Trades',
                _DOCUMENT,
                'unified:orders:trades',
                'Today\'s trades at every broker, combined every half second.',
                needs_broker=False,
            ),
            self._view(
                'holdings',
                'Holdings',
                _DOCUMENT,
                'unified:portfolio:holdings',
                'Holdings merged across every broker and priced, combined every minute.',
                needs_broker=False,
            ),
            self._view(
                'positions',
                'Positions',
                _DOCUMENT,
                'unified:portfolio:positions',
                'Open positions, net and day, merged across every broker every half second.',
                needs_broker=False,
            ),
            self._view(
                'funds',
                'Funds',
                _DOCUMENT,
                'unified:portfolio:funds',
                'Funds summed across every broker every half second.',
                needs_broker=False,
            ),
        ]

    def _view(
        self,
        name: str,
        label: str,
        kind: str,
        key: str,
        note: str,
        needs_broker: bool = True,
        field: str | None = None,
    ) -> dict[str, Any]:
        """Describes one tab.

        Args:
            name (str): The name the browser asks for the tab by.
            label (str): The human label.
            kind (str): How the key is read: "document", "hash_field", "hash_documents" or "table".
            key (str): The Redis key, where "{broker}" stands for the chosen broker.
            note (str): One sentence saying what the tab shows.
            needs_broker (bool): Whether a broker must be chosen before the tab can be read.
            field (str | None): The hash field to read, for a "hash_field" tab, where "{broker}" stands for the chosen broker.

        Returns:
            dict[str, Any]: The tab.
        """
        return {
            'name': name,
            'label': label,
            'kind': kind,
            'key': key,
            'note': note,
            'needs_broker': needs_broker,
            'field': field,
        }

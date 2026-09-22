"""Tests for the live view's Redis readers and the catalogue that keeps them to known keys."""

import json

import pytest

from system_monitor.live.broker_instruments_table import BrokerInstrumentsTable
from system_monitor.live.broker_mapping_table import BrokerMappingTable
from system_monitor.live.live_view_reader import LiveViewReader, UnknownViewError
from system_monitor.live.unified_instruments_table import UnifiedInstrumentsTable
from system_monitor.live.view_catalogue import ViewCatalogue
from system_monitor.sources.unit_inventory import UnitInventory
from tests.fakes import FakeRedisReader


class _Inventory(UnitInventory):
    """An inventory that reports a fixed list of brokers."""

    def __init__(self, brokers: list[str]):
        """Creates the inventory.

        Args:
            brokers (list[str]): The broker names to report.
        """
        self._brokers = brokers

    def brokers(self) -> list[str]:
        """Lists the fixed brokers.

        Returns:
            list[str]: The broker names.
        """
        return list(self._brokers)


def _reader(redis_reader: FakeRedisReader) -> LiveViewReader:
    """Builds a live view reader over a fake Redis.

    Args:
        redis_reader (FakeRedisReader): The store to read.

    Returns:
        LiveViewReader: The reader, offering zerodha and dhan.
    """
    return LiveViewReader(
        redis_reader,
        ViewCatalogue(),
        _Inventory(
            [
                'zerodha',
                'dhan',
            ],
        ),
    )


class TestDocumentViews:
    """Reading the tabs that show one stored document."""

    def test_broker_session_status_is_returned_whole(self):
        """A session document is returned exactly as Redis holds it, token included."""
        redis_reader = FakeRedisReader()
        redis_reader.set_json(
            'zerodha:session:status',
            {
                'status': 'success',
                'access-token': 'a-real-token',
                'last_login': '2026-09-22 06:31:35',
            },
        )
        answer = _reader(redis_reader).read_view('broker', 'session_status', 'zerodha')
        assert answer['value']['key'] == 'zerodha:session:status'
        assert answer['value']['exists'] is True
        assert answer['value']['document']['access-token'] == 'a-real-token'

    def test_a_missing_key_reads_as_absent_rather_than_failing(self):
        """The unified session key is simply absent on a system where its writer has not run."""
        answer = _reader(FakeRedisReader()).read_view('unified', 'session_status', None)
        assert answer['value']['exists'] is False
        assert answer['value']['document'] is None

    def test_a_value_that_is_not_json_is_returned_as_text(self):
        """A key holding something other than JSON is shown rather than refused."""
        redis_reader = FakeRedisReader()
        redis_reader.strings['unified:portfolio:funds'] = 'not json at all'
        answer = _reader(redis_reader).read_view('unified', 'funds', None)
        assert answer['value']['document'] is None
        assert answer['value']['text'] == 'not json at all'

    def test_a_hash_field_tab_reads_the_named_field(self):
        """The application token tab reads one field of the shared last_login hash."""
        redis_reader = FakeRedisReader()
        redis_reader.set_hash_json(
            'last_login',
            'unified_broker_interface',
            {
                'access_token': 'application-token',
            },
        )
        answer = _reader(redis_reader).read_view('unified', 'application_token', None)
        assert answer['value']['field'] == 'unified_broker_interface'
        assert answer['value']['document']['access_token'] == 'application-token'

    def test_a_broker_hash_field_tab_reads_that_broker_s_field(self):
        """The stored login tab reads the chosen broker's own field."""
        redis_reader = FakeRedisReader()
        redis_reader.set_hash_json(
            'last_login',
            'dhan',
            {
                'broker_name': 'dhan',
            },
        )
        answer = _reader(redis_reader).read_view('broker', 'stored_login', 'dhan')
        assert answer['value']['field'] == 'dhan'
        assert answer['value']['document']['broker_name'] == 'dhan'

    def test_a_hash_of_documents_returns_every_entry_and_its_poll_time(self):
        """A broker's orders are one entry per order, beside the time the book was last read."""
        redis_reader = FakeRedisReader()
        redis_reader.set_hash_json(
            'zerodha:orders:orders',
            '2611',
            {
                'source': 'rest',
            },
        )
        redis_reader.set_hash_json(
            'zerodha:orders:orders',
            '1907',
            {
                'source': 'websocket',
            },
        )
        redis_reader.strings['zerodha:orders:orders:polled_at'] = '1790074995'
        answer = _reader(redis_reader).read_view('broker', 'orders', 'zerodha')
        assert answer['value']['field_count'] == 2
        assert [entry['field'] for entry in answer['value']['entries']] == [
            '1907',
            '2611',
        ]
        assert answer['value']['polled_at'] == '1790074995'


class TestCatalogueRefusals:
    """The browser can only name tabs the catalogue holds."""

    def test_an_unknown_tab_is_refused(self):
        """A name that is not in the catalogue never becomes a Redis read."""
        with pytest.raises(UnknownViewError):
            _reader(FakeRedisReader()).read_view('broker', 'anything_else', 'zerodha')

    def test_an_unknown_scope_is_refused(self):
        """A scope other than broker or unified holds no tabs at all."""
        with pytest.raises(UnknownViewError):
            _reader(FakeRedisReader()).read_view('secrets', 'session_status', 'zerodha')

    def test_a_broker_tab_without_a_broker_is_refused(self):
        """A tab whose key names a broker cannot be read without one."""
        with pytest.raises(ValueError, match='needs a broker'):
            _reader(FakeRedisReader()).read_view('broker', 'session_status', None)

    def test_a_broker_outside_the_inventory_is_refused(self):
        """A broker name the inventory does not know never reaches a key.

        This is what stops a chosen broker from being used to build an arbitrary key.
        """
        with pytest.raises(ValueError, match='Not a unified_broker_interface broker'):
            _reader(FakeRedisReader()).read_view('broker', 'session_status', 'elsewhere')

    def test_a_table_cannot_be_read_as_a_document(self):
        """The huge tables are refused by the document route, which would send them whole."""
        with pytest.raises(UnknownViewError, match='is a table'):
            _reader(FakeRedisReader()).read_view('unified', 'instruments_master', None)

    def test_a_document_cannot_be_read_as_a_table(self):
        """A document tab is refused by the table route rather than answered with nothing."""
        with pytest.raises(UnknownViewError, match='is not a table'):
            _reader(FakeRedisReader()).read_table('unified', 'funds', None, '0', 10, None)


class TestRowTables:
    """Paging and searching the three hashes of JSON array rows."""

    def _instruments(self, count: int) -> FakeRedisReader:
        """Builds a fake Redis holding a unified instruments table.

        Args:
            count (int): How many instruments to store.

        Returns:
            FakeRedisReader: The store, with its mapping meta document.
        """
        redis_reader = FakeRedisReader()
        redis_reader.set_json(
            'unified:mapping:meta',
            {
                'mapping_date': '2026-09-22',
                'columns': {
                    'instruments': [
                        'exchange',
                        'segment',
                        'symbol',
                    ],
                    'broker_mappings': [
                        'broker_token',
                        'broker_symbol',
                    ],
                },
            },
        )
        for index in range(count):
            redis_reader.hashes.setdefault('unified:instruments', {})[f'id-{index:04d}'] = json.dumps(
                [
                    'nse',
                    'nse_equities',
                    f'SYMBOL{index}',
                ],
            )
        return redis_reader

    def test_columns_come_from_the_meta_document(self):
        """The rows are bare arrays, so the column names are read from the meta document."""
        table = UnifiedInstrumentsTable(self._instruments(3))
        assert table.columns() == [
            'exchange',
            'segment',
            'symbol',
        ]

    def test_a_page_stops_near_the_limit_rather_than_at_a_fixed_batch(self):
        """A small page must not drag back a whole scan batch."""
        page = UnifiedInstrumentsTable(self._instruments(1000)).page('0', 100)
        assert len(page['rows']) == 100
        assert page['total_fields'] == 1000
        assert page['cursor'] is not None

    def test_paging_walks_the_whole_hash_without_repeating_a_row(self):
        """Following the cursor to the end returns every row exactly once."""
        table = UnifiedInstrumentsTable(self._instruments(250))
        seen = []
        cursor = '0'
        while cursor is not None:
            page = table.page(cursor, 100)
            seen.extend(row['key'] for row in page['rows'])
            cursor = page['cursor']
        assert len(seen) == 250
        assert len(set(seen)) == 250

    def test_the_last_page_reports_no_cursor(self):
        """A hash smaller than one page ends immediately."""
        page = UnifiedInstrumentsTable(self._instruments(10)).page('0', 100)
        assert page['cursor'] is None
        assert len(page['rows']) == 10

    def test_a_cursor_that_is_not_a_number_is_refused(self):
        """A cursor is a number Redis gave out, not free text."""
        with pytest.raises(ValueError, match='Not a cursor'):
            UnifiedInstrumentsTable(self._instruments(10)).page('not-a-number', 100)

    def test_a_search_matches_a_cell_without_regard_to_case(self):
        """Searching looks inside the row's cells, not only at its key."""
        found = UnifiedInstrumentsTable(self._instruments(200)).search('symbol137', 50)
        assert [row['key'] for row in found['rows']] == [
            'id-0137',
        ]
        assert found['search'] == 'symbol137'
        assert found['complete'] is True

    def test_a_search_stops_at_its_row_limit_and_says_so(self):
        """A search that fills up is reported as incomplete rather than as the whole answer."""
        found = UnifiedInstrumentsTable(self._instruments(200)).search('nse_equities', 20)
        assert len(found['rows']) == 20
        assert found['complete'] is False

    def test_a_broker_instruments_table_takes_its_columns_from_the_broker_s_meta(self):
        """Each broker's instrument file has its own columns, named in its own meta document."""
        redis_reader = FakeRedisReader()
        redis_reader.set_json(
            'zerodha:instruments:meta',
            {
                'download_date': '2026-09-22',
                'columns': [
                    'instrument_token',
                    'tradingsymbol',
                ],
            },
        )
        redis_reader.hashes['zerodha:instruments:master'] = {
            '28052482': json.dumps(
                [
                    '28052482',
                    'HDFCLIFE26SEP460PE',
                ],
            ),
        }
        page = BrokerInstrumentsTable(redis_reader, 'zerodha').page('0', 10)
        assert page['columns'] == [
            'instrument_token',
            'tradingsymbol',
        ]
        assert page['rows'][0]['values'][1] == 'HDFCLIFE26SEP460PE'

    def test_the_mapping_table_keeps_only_the_chosen_broker_s_fields(self):
        """Every broker shares one mapping hash, so the broker's prefix is what selects its rows."""
        redis_reader = self._instruments(0)
        redis_reader.hashes['unified:broker_mappings'] = {
            'zerodha:id-0001': json.dumps(
                [
                    '21939970',
                    'ZERODHA-SYMBOL',
                ],
            ),
            'dhan:id-0001': json.dumps(
                [
                    '2885',
                    'DHAN-SYMBOL',
                ],
            ),
            'zerodha:id-0002': json.dumps(
                [
                    '11111',
                    'ANOTHER-ZERODHA',
                ],
            ),
        }
        page = BrokerMappingTable(redis_reader, 'zerodha').page('0', 100)
        assert [row['key'] for row in page['rows']] == [
            'id-0001',
            'id-0002',
        ]

    def test_the_mapping_table_removes_the_broker_from_the_key_it_shows(self):
        """The row is about an instrument, so its key is the instrument id and not the prefixed field."""
        redis_reader = self._instruments(0)
        redis_reader.hashes['unified:broker_mappings'] = {
            'zerodha:id-0001': json.dumps(
                [
                    '21939970',
                ],
            ),
        }
        page = BrokerMappingTable(redis_reader, 'zerodha').page('0', 100)
        assert page['rows'][0]['key'] == 'id-0001'
        assert page['key_column'] == 'instrument_id'
        assert page['field_prefix'] == 'zerodha:'


class TestViewCatalogue:
    """The declared tabs themselves."""

    def test_every_tab_has_a_reader_that_can_build_it(self):
        """A tab nobody can read would be a dead entry in the page's navigation."""
        catalogue = ViewCatalogue()
        for scope in catalogue.scopes():
            for view in catalogue.views(scope):
                assert view['kind'] in (
                    'document',
                    'hash_field',
                    'hash_documents',
                    'table',
                )
                assert view['label']
                assert view['note']

    def test_no_tab_reads_a_key_outside_ubi_s_namespaces(self):
        """The set of readable keys is what this catalogue says it is, and nothing wider."""
        catalogue = ViewCatalogue()
        for scope in catalogue.scopes():
            for name in [view['name'] for view in catalogue.views(scope)]:
                key = catalogue.find(scope, name)['key']
                assert key.startswith(('unified:', '{broker}:')) or key == 'last_login'

    def test_a_broker_key_is_built_from_the_chosen_broker(self):
        """The broker fills the one placeholder in the key, and nothing else does."""
        catalogue = ViewCatalogue()
        view = catalogue.find('broker', 'holdings')
        assert catalogue.key_for(view, 'dhan') == 'dhan:portfolio:holdings'

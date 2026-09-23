"""Tests for JournalClient."""

import json

from system_monitor.sources.journal_client import JournalClient
from tests.fakes import FakeCommandRunner


class TestJournalClient:
    """Tests for JournalClient."""

    def _line(self, message: object, cursor: str = 'c1') -> str:
        """Builds one journalctl JSON line.

        Args:
            message (object): The MESSAGE field value.
            cursor (str): The cursor value.

        Returns:
            str: The JSON line.
        """
        return json.dumps(
            {
                '__CURSOR': cursor,
                '__REALTIME_TIMESTAMP': '1789436180591829',
                '_SYSTEMD_USER_UNIT': 'zerodha-instruments@websocket_quotes.service',
                'SYSLOG_IDENTIFIER': 'zerodha-quotes',
                'MESSAGE': message,
            },
        )

    def test_parse_line_reads_fields(self):
        """Checks that the fields and the microsecond timestamp are read.

        Raises:
            AssertionError: A field is wrong.
        """
        entry = JournalClient(FakeCommandRunner()).parse_line(self._line('hello'))
        assert entry.unit == 'zerodha-instruments@websocket_quotes.service'
        assert entry.identifier == 'zerodha-quotes'
        assert entry.message == 'hello'
        assert entry.timestamp == 1789436180.591829

    def test_parse_line_decodes_byte_arrays(self):
        """Checks that a MESSAGE printed as byte values becomes text.

        Raises:
            AssertionError: The message was not decoded.
        """
        entry = JournalClient(FakeCommandRunner()).parse_line(
            self._line(
                [
                    104,
                    105,
                ],
            ),
        )
        assert entry.message == 'hi'

    def test_parse_line_ignores_garbage(self):
        """Checks that blank and non-JSON lines give None.

        Raises:
            AssertionError: A garbage line produced an entry.
        """
        client = JournalClient(FakeCommandRunner())
        assert client.parse_line('') is None
        assert client.parse_line('not json') is None

    def test_read_after_cursor_uses_cursor_or_since(self):
        """Checks that a cursor is preferred and a time is used without one.

        Raises:
            AssertionError: The arguments are wrong.
        """
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'journalctl',
            ],
            self._line('one', 'c1') + '\n' + self._line('two', 'c2') + '\n',
        )
        client = JournalClient(runner)
        entries = client.read_after_cursor(None, since_epoch=1789436000.7)
        assert [entry.cursor for entry in entries] == [
            'c1',
            'c2',
        ]
        assert '--since=@1789436000' in runner.calls[0]
        client.read_after_cursor('c2', since_epoch=0)
        assert '--after-cursor=c2' in runner.calls[1]

"""Tests for LogLineParser."""

from system_monitor.sources.log_line_parser import LogLineParser

_UNIT = 'zerodha@quotes.service'


class TestLogLineParser:
    """Tests for LogLineParser.parse."""

    def test_parse_reads_warning_from_text(self):
        """Checks the real line that the journal stores at priority 6.

        Raises:
            AssertionError: The level or logger name is wrong.
        """
        parser = LogLineParser()
        parsed = parser.parse(_UNIT, '2026-09-15 07:06:20 WARNING  zerodha.quotes socket_0 disconnected. Reconnecting in 1 seconds.')
        assert parsed.level == 'WARNING'
        assert parsed.logger_name == 'zerodha.quotes'
        assert not parsed.is_continuation

    def test_parse_accepts_milliseconds(self):
        """Checks the default logging time format with a comma and milliseconds.

        Raises:
            AssertionError: The level is wrong.
        """
        parser = LogLineParser()
        parsed = parser.parse(_UNIT, '2026-09-15 07:06:20,123 ERROR    unified.quotes failed')
        assert parsed.level == 'ERROR'

    def test_parse_traceback_lines_are_errors(self):
        """Checks that a traceback and its following lines are errors even after an INFO line.

        Raises:
            AssertionError: A traceback line is not an error.
        """
        parser = LogLineParser()
        parser.parse(_UNIT, '2026-09-15 07:06:21 INFO     zerodha.quotes socket_0 opened')
        assert parser.parse(_UNIT, 'Traceback (most recent call last):').level == 'ERROR'
        continuation = parser.parse(_UNIT, '  File "bin/zerodha/quotes", line 10, in <module>')
        assert continuation.level == 'ERROR'
        assert continuation.is_continuation

    def test_parse_continuation_inherits_per_unit(self):
        """Checks that each unit remembers its own last level.

        Raises:
            AssertionError: A continuation took another unit's level.
        """
        parser = LogLineParser()
        parser.parse('a.service', '2026-09-15 07:06:21 ERROR    a boom')
        parser.parse('b.service', '2026-09-15 07:06:21 INFO     b fine')
        assert parser.parse('a.service', 'details').level == 'ERROR'
        assert parser.parse('b.service', 'details').level == 'INFO'

    def test_parse_unknown_first_line_is_info(self):
        """Checks that a plain line with no earlier record is INFO.

        Raises:
            AssertionError: The level is not INFO.
        """
        parser = LogLineParser()
        assert parser.parse(_UNIT, 'plain print output').level == 'INFO'

"""Tests for TextFormatter."""

from system_monitor.utilities.text_formatter import TextFormatter
from tests.fakes import FixedClock


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_duration_uses_two_largest_units(self):
        """Checks each duration range.

        Raises:
            AssertionError: A description is wrong.
        """
        assert TextFormatter.duration(-3) == '0 s'
        assert TextFormatter.duration(45) == '45 s'
        assert TextFormatter.duration(180) == '3 min'
        assert TextFormatter.duration(195) == '3 min 15 s'
        assert TextFormatter.duration(7500) == '2 h 5 min'
        assert TextFormatter.duration(3 * 86400 + 4 * 3600) == '3 d 4 h'

    def test_count_picks_singular_or_plural(self):
        """Checks singular and plural nouns.

        Raises:
            AssertionError: A form is wrong.
        """
        assert TextFormatter.count(1, 'error') == '1 error'
        assert TextFormatter.count(0, 'warning') == '0 warnings'
        assert TextFormatter.count(15, 'error') == '15 errors'

    def test_india_time_adds_date_only_for_other_days(self):
        """Checks today's and yesterday's times.

        Raises:
            AssertionError: A description is wrong.
        """
        now = FixedClock.at_india_time(2026, 9, 15, 15, 0).now()
        assert TextFormatter.india_time(FixedClock.at_india_time(2026, 9, 15, 8, 30).now(), now) == '08:30'
        assert TextFormatter.india_time(FixedClock.at_india_time(2026, 9, 14, 13, 54).now(), now) == '14 Sep 13:54'

"""Tests for loading thresholds.toml."""

import copy
import datetime
import tomllib
from pathlib import Path

import pytest

from system_monitor.configuration import thresholds

_PROJECT_THRESHOLDS = Path(__file__).resolve().parent.parent / 'thresholds.toml'


class TestThresholds:
    """Tests for Thresholds.load and Thresholds.from_dictionary."""

    def _document(self) -> dict:
        """Reads the project's own thresholds file as a dictionary.

        Returns:
            dict: The parsed TOML document.
        """
        with _PROJECT_THRESHOLDS.open('rb') as file:
            return tomllib.load(file)

    def test_load_reads_project_file(self):
        """Checks that the shipped thresholds file loads with the expected values.

        Raises:
            AssertionError: A value differs from the file.
        """
        loaded = thresholds.Thresholds.load(_PROJECT_THRESHOLDS)
        assert loaded.feeds.default_limits.warning_age_seconds == 45
        assert loaded.feeds.limits_for('stoxkart').failure_age_seconds == 900
        assert loaded.feeds.limits_for('zerodha').failure_age_seconds == 120
        assert loaded.streams.cap_for('broker_quotes') == 1000000
        assert loaded.streams.cap_for('unified_quotes') == 1000000
        assert loaded.streams.cap_for('broker_order_updates') == 20000
        assert loaded.reference_data.expected_by == datetime.time(9, 0)
        assert loaded.alerts.consecutive_failures == 2

    def test_from_dictionary_missing_section_raises(self):
        """Checks that a missing section is reported by name.

        Raises:
            AssertionError: No error, or an error without the section name.
        """
        document = self._document()
        del document['alerts']
        with pytest.raises(ValueError, match=r'\[alerts\]'):
            thresholds.Thresholds.from_dictionary(document)

    def test_from_dictionary_wrong_type_raises(self):
        """Checks that a value of the wrong type is reported with its key.

        Raises:
            AssertionError: No error, or an error without the key name.
        """
        document = copy.deepcopy(self._document())
        document['feeds']['warning_age_seconds'] = 'soon'
        with pytest.raises(ValueError, match='warning_age_seconds'):
            thresholds.Thresholds.from_dictionary(document)

    def test_cap_for_unknown_kind_raises(self):
        """Checks that asking for an unconfigured stream cap is an error.

        Raises:
            AssertionError: No error was raised.
        """
        loaded = thresholds.Thresholds.load(_PROJECT_THRESHOLDS)
        with pytest.raises(ValueError, match='unknown_kind'):
            loaded.streams.cap_for('unknown_kind')

"""Tests for UnitInventory."""

from system_monitor.sources.systemd_client import SystemdClient
from system_monitor.sources.unit_inventory import UnitInventory, UnitKind
from tests.fakes import FakeCommandRunner


class TestUnitInventory:
    """Tests for UnitInventory."""

    def _inventory(self, tmp_path) -> UnitInventory:
        """Builds an inventory over a fake services directory with zerodha, kotak, databases and unified.

        kotak's target has no members, as if it were not installed.

        Args:
            tmp_path (pathlib.Path): pytest's temporary directory.

        Returns:
            UnitInventory: The refreshed inventory.
        """
        for name in (
            'zerodha',
            'unified',
            'kotak',
            'databases',
        ):
            (tmp_path / name).mkdir()
        (tmp_path / 'README.md').write_text('not a subject')
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'systemctl',
                '--user',
                'list-dependencies',
                'zerodha.target',
            ],
            'zerodha.target\n  zerodha-historical-prices.service\n  zerodha-login.service\n  zerodha-login.timer\n  zerodha@quotes.service\n',
        )
        runner.add_response(
            [
                'systemctl',
                '--user',
                'list-dependencies',
                'unified.target',
            ],
            'unified.target\n  unified-rest-api.service\n',
        )
        runner.add_response(
            [
                'systemctl',
                '--user',
                'list-dependencies',
                'kotak.target',
            ],
            'kotak.target\n',
        )
        runner.add_response(
            [
                'systemctl',
                '--user',
                'list-dependencies',
                'databases.target',
            ],
            'databases.target\n  databases.service\n  databases.timer\n',
        )
        inventory = UnitInventory(SystemdClient(runner), tmp_path)
        inventory.refresh()
        return inventory

    def test_refresh_orders_subjects_unified_last(self, tmp_path):
        """Checks the subject order and that the broker list leaves out databases and unified.

        Raises:
            AssertionError: The order is wrong or a non-broker subject is listed as a broker.
        """
        inventory = self._inventory(tmp_path)
        assert inventory.subjects() == [
            'kotak',
            'zerodha',
            'databases',
            'unified',
        ]
        assert inventory.brokers() == [
            'kotak',
            'zerodha',
        ]

    def test_refresh_classifies_kinds(self, tmp_path):
        """Checks that timers, scheduled, periodic and long-running units are told apart.

        Raises:
            AssertionError: A kind is wrong.
        """
        inventory = self._inventory(tmp_path)
        assert inventory.find('zerodha-login.timer').kind == UnitKind.TIMER
        assert inventory.find('zerodha-login.service').kind == UnitKind.SCHEDULED
        assert inventory.find('zerodha-historical-prices.service').kind == UnitKind.PERIODIC
        assert inventory.find('zerodha@quotes.service').kind == UnitKind.LONG_RUNNING
        assert inventory.find('unified-rest-api.service').subject == 'unified'

    def test_refresh_keeps_database_units(self, tmp_path):
        """Checks that the database units are still watched, under their own subject.

        Raises:
            AssertionError: A database unit is missing or has the wrong subject or kind.
        """
        inventory = self._inventory(tmp_path)
        service = inventory.find('databases.service')
        timer = inventory.find('databases.timer')
        assert service.subject == 'databases'
        assert service.kind == UnitKind.SCHEDULED
        assert timer.subject == 'databases'
        assert timer.kind == UnitKind.TIMER

    def test_refresh_records_missing_targets(self, tmp_path):
        """Checks that a target with no members is reported.

        Raises:
            AssertionError: The missing target is not listed.
        """
        inventory = self._inventory(tmp_path)
        assert inventory.missing_targets() == [
            'kotak.target',
        ]

    def test_has_unit_requires_exact_name(self, tmp_path):
        """Checks that lookups never match partial names.

        Raises:
            AssertionError: A partial or foreign name matched.
        """
        inventory = self._inventory(tmp_path)
        assert inventory.has_unit('zerodha@quotes.service')
        assert not inventory.has_unit('zerodha@quotes')
        assert not inventory.has_unit('ssh.service')

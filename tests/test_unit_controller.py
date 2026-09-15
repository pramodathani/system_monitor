"""Tests for UnitController."""

import pytest

from system_monitor.controls.unit_controller import UnitController, UnitNotAllowedError
from system_monitor.sources.command_runner import CommandResult
from tests.fakes import FakeSystemdClient, FakeUnitInventory, FixedClock


class TestUnitController:
    """Tests for UnitController."""

    def _controller(self) -> tuple[UnitController, FakeSystemdClient]:
        """Builds a controller over zerodha's quotes service and login timer.

        Returns:
            tuple[UnitController, FakeSystemdClient]: A tuple (controller, systemd client).
        """
        inventory = FakeUnitInventory(
            {
                'zerodha': [
                    'zerodha@quotes.service',
                    'zerodha-login.service',
                    'zerodha-login.timer',
                ],
            },
        )
        systemd_client = FakeSystemdClient()
        return UnitController(systemd_client, inventory, FixedClock(50.0)), systemd_client

    def test_perform_records_allowed_action(self):
        """Checks a restart of an inventory service.

        Raises:
            AssertionError: The action was not run or not recorded.
        """
        controller, systemd_client = self._controller()
        recorded = controller.perform('zerodha@quotes.service', 'restart', '192.0.2.5')
        assert recorded.succeeded
        assert systemd_client.actions == [
            ('restart', 'zerodha@quotes.service'),
        ]
        assert controller.recent_actions()[0]['address'] == '192.0.2.5'
        assert controller.version == 1

    def test_perform_rejects_units_outside_inventory_and_timers(self):
        """Checks that foreign units and timers are refused without running anything.

        Raises:
            AssertionError: A refused unit was acted on.
        """
        controller, systemd_client = self._controller()
        for unit_name in (
            'ssh.service',
            'zerodha@quotes',
            'zerodha-login.timer',
            'zerodha@quotes.service; rm -rf ~',
        ):
            with pytest.raises(UnitNotAllowedError):
                controller.perform(unit_name, 'restart', '192.0.2.5')
        assert systemd_client.actions == []

    def test_perform_rejects_stop(self):
        """Checks that stop is not an action.

        Raises:
            AssertionError: No error was raised.
        """
        controller, _systemd_client = self._controller()
        with pytest.raises(ValueError, match='stop'):
            controller.perform('zerodha@quotes.service', 'stop', '192.0.2.5')

    def test_perform_records_systemctl_refusal(self):
        """Checks that a systemctl error is recorded as a failed action.

        Raises:
            AssertionError: The failure was not recorded.
        """
        controller, systemd_client = self._controller()

        def refuse(action: str, unit_name: str) -> CommandResult:
            """Refuses every action.

            Args:
                action (str): Ignored.
                unit_name (str): Ignored.

            Returns:
                CommandResult: A failed result.
            """
            del action, unit_name
            return CommandResult(1, '', 'Access denied')

        systemd_client.run_unit_action = refuse
        recorded = controller.perform('zerodha-login.service', 'start', '192.0.2.5')
        assert not recorded.succeeded
        assert 'Access denied' in recorded.message

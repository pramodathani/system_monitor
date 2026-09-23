"""Tests for SystemdClient."""

import pytest

from system_monitor.sources.systemd_client import SystemdClient, SystemdError
from tests.fakes import FakeCommandRunner


class TestSystemdClient:
    """Tests for SystemdClient."""

    def test_list_target_members_skips_target_line(self):
        """Checks that the first line, the target itself, is not a member.

        Raises:
            AssertionError: The members are wrong.
        """
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'systemctl',
                '--user',
                'list-dependencies',
            ],
            'stoxkart.target\n  stoxkart-login.service\n  stoxkart-login.timer\n  stoxkart-portfolio@funds.service\n',
        )
        members = SystemdClient(runner).list_target_members('stoxkart.target')
        assert members == [
            'stoxkart-login.service',
            'stoxkart-login.timer',
            'stoxkart-portfolio@funds.service',
        ]

    def test_show_units_parses_blocks_by_id(self):
        """Checks that blank-line separated blocks are keyed by Id.

        Raises:
            AssertionError: The parsed properties are wrong.
        """
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'systemctl',
                '--user',
                'show',
            ],
            'Id=a.service\nActiveState=active\nExecMainStartTimestamp=@1789377075\n\nActiveState=failed\nId=b.service\n',
        )
        client = SystemdClient(runner)
        units = client.show_units(
            [
                'a.service',
                'b.service',
            ],
            [
                'ActiveState',
            ],
        )
        assert units['a.service']['ExecMainStartTimestamp'] == '@1789377075'
        assert units['b.service']['ActiveState'] == 'failed'
        assert '--property=Id,ActiveState' in runner.calls[0]

    def test_show_units_error_raises(self):
        """Checks that a failing systemctl raises SystemdError.

        Raises:
            AssertionError: No error was raised.
        """
        runner = FakeCommandRunner()
        runner.add_response(
            [
                'systemctl',
            ],
            return_code=1,
            standard_error='Failed to connect to bus',
        )
        with pytest.raises(SystemdError, match='Failed to connect to bus'):
            SystemdClient(runner).show_units(
                [
                    'a.service',
                ],
                [
                    'ActiveState',
                ],
            )

    def test_run_unit_action_uses_no_block(self):
        """Checks that restarts never wait for the unit.

        Raises:
            AssertionError: The command is wrong.
        """
        runner = FakeCommandRunner()
        SystemdClient(runner).run_unit_action('restart', 'unified-user@details.service')
        assert runner.calls[0] == [
            'systemctl',
            '--user',
            'restart',
            '--no-block',
            'unified-user@details.service',
        ]

    def test_run_unit_action_rejects_stop(self):
        """Checks that only start and restart are accepted.

        Raises:
            AssertionError: No error was raised.
        """
        with pytest.raises(ValueError, match='stop'):
            SystemdClient(FakeCommandRunner()).run_unit_action('stop', 'a.service')

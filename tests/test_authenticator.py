"""Tests for Authenticator."""

import argon2

from system_monitor.security.authenticator import Authenticator
from tests.fakes import FixedClock

_HASH = argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash('correct horse battery')


class TestAuthenticator:
    """Tests for Authenticator."""

    def test_verify_accepts_correct_password(self):
        """Checks the right password.

        Raises:
            AssertionError: The password was rejected.
        """
        authenticator = Authenticator(_HASH, FixedClock(0))
        assert authenticator.verify('192.0.2.1', 'correct horse battery')

    def test_verify_locks_out_after_repeated_failures(self):
        """Checks that five failures lock one address out, not others, until the period passes.

        Raises:
            AssertionError: The lockout is wrong.
        """
        clock = FixedClock(0)
        authenticator = Authenticator(_HASH, clock, maximum_failures=5, lockout_seconds=300)
        for _attempt in range(4):
            assert not authenticator.verify('192.0.2.1', 'wrong')
        assert not authenticator.is_locked_out('192.0.2.1')
        assert not authenticator.verify('192.0.2.1', 'wrong')
        assert authenticator.is_locked_out('192.0.2.1')
        assert not authenticator.is_locked_out('192.0.2.2')
        clock.advance(301)
        assert not authenticator.is_locked_out('192.0.2.1')

    def test_verify_success_clears_failures(self):
        """Checks that a correct password forgets earlier failures.

        Raises:
            AssertionError: Failures were remembered.
        """
        authenticator = Authenticator(_HASH, FixedClock(0), maximum_failures=2)
        authenticator.verify('192.0.2.1', 'wrong')
        authenticator.verify('192.0.2.1', 'correct horse battery')
        authenticator.verify('192.0.2.1', 'wrong')
        assert not authenticator.is_locked_out('192.0.2.1')

    def test_verify_rejects_invalid_hash(self):
        """Checks that a corrupted hash rejects every password instead of raising.

        Raises:
            AssertionError: The password was accepted or an error escaped.
        """
        authenticator = Authenticator('not-a-hash', FixedClock(0))
        assert not authenticator.verify('192.0.2.1', 'anything')

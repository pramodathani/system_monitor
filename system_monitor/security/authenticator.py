"""Checks the dashboard password and locks out an address after repeated failures.

Typical usage example:

  authenticator = Authenticator(settings.password_hash, SystemClock())
  if authenticator.is_locked_out(address):
      ...
  elif authenticator.verify(address, password):
      ...
"""

import collections
import threading

import argon2
import argon2.exceptions

from system_monitor.utilities.clock import SystemClock


class Authenticator:
    """Verifies the single dashboard password with argon2."""

    def __init__(
        self,
        password_hash: str,
        clock: SystemClock,
        maximum_failures: int = 5,
        lockout_seconds: float = 300.0,
    ):
        """Creates the authenticator.

        Args:
            password_hash (str): The argon2 hash of the password.
            clock (SystemClock): The source of the current time.
            maximum_failures (int): How many failures within the lockout period lock an address out.
            lockout_seconds (float): How long failures are remembered.
        """
        self.password_hash = password_hash
        self.clock = clock
        self.maximum_failures = maximum_failures
        self.lockout_seconds = lockout_seconds
        self._hasher = argon2.PasswordHasher()
        self._failures_by_address = {}
        self._lock = threading.Lock()

    def is_locked_out(self, address: str) -> bool:
        """Checks whether an address has failed too often recently.

        Args:
            address (str): The client's network address.

        Returns:
            bool: True when the address must wait before trying again.
        """
        with self._lock:
            failures = self._recent_failures(address)
            return len(failures) >= self.maximum_failures

    def verify(self, address: str, password: str) -> bool:
        """Checks a password, recording a failure for the address when it is wrong.

        Args:
            address (str): The client's network address.
            password (str): The password typed in.

        Returns:
            bool: True when the password matches.
        """
        try:
            self._hasher.verify(self.password_hash, password)
        except (argon2.exceptions.VerificationError, argon2.exceptions.InvalidHashError):
            with self._lock:
                self._recent_failures(address).append(self.clock.now())
            return False
        with self._lock:
            self._failures_by_address.pop(address, None)
        return True

    def _recent_failures(self, address: str) -> collections.deque:
        """Finds an address's failures, forgetting those older than the lockout period.

        The caller must hold the lock.

        Args:
            address (str): The client's network address.

        Returns:
            collections.deque: The failure times still remembered, oldest first.
        """
        failures = self._failures_by_address.get(address)
        if failures is None:
            failures = collections.deque()
            self._failures_by_address[address] = failures
        oldest_kept = self.clock.now() - self.lockout_seconds
        while failures and failures[0] < oldest_kept:
            failures.popleft()
        return failures

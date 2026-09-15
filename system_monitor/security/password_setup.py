"""Prompts for a dashboard password and prints the lines to put in .env.

Run it through `bin/set-password`. It prints a new session secret as well, so running it again also logs every browser out.

Typical usage example:

  PasswordSetup().run()
"""

import getpass
import secrets
import sys

import argon2

_MINIMUM_LENGTH = 12


class PasswordSetup:
    """An interactive tool that hashes a new password."""

    def run(self) -> int:
        """Asks for the password twice and prints the .env lines.

        Returns:
            int: 0 on success, 1 when the passwords differ or are too short.
        """
        password = getpass.getpass('New dashboard password: ')
        repeated = getpass.getpass('Repeat the password: ')
        if password != repeated:
            print('The passwords differ; nothing was changed.', file=sys.stderr)
            return 1
        if len(password) < _MINIMUM_LENGTH:
            print(f'Use at least {_MINIMUM_LENGTH} characters; nothing was changed.', file=sys.stderr)
            return 1
        password_hash = argon2.PasswordHasher().hash(password)
        session_secret = secrets.token_urlsafe(48)
        print('Put these two lines in .env, replacing any existing ones, then restart the monitor:')
        print(f"SYSTEM_MONITOR_PASSWORD_HASH='{password_hash}'")
        print(f"SYSTEM_MONITOR_SESSION_SECRET='{session_secret}'")
        return 0


if __name__ == '__main__':
    sys.exit(PasswordSetup().run())

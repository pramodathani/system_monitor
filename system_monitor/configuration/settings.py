"""The monitor's own settings, read from SYSTEM_MONITOR_* environment variables.

The values come from the process environment first and then from the `.env` file in the working directory. `bin/system-monitor` changes into the project directory before starting, so the relative paths below resolve against the project root.

Typical usage example:

  settings = Settings()
  settings.require_security_values()
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The monitor's settings.

    Attributes:
        host: The address the web server listens on.
        port: The port the web server listens on.
        password_hash: The argon2 hash of the dashboard password, produced by bin/set-password.
        session_secret: The secret that signs the session cookie.
        session_max_age_seconds: How long a login lasts, in seconds.
        unified_broker_interface_directory: The directory of the unified_broker_interface project.
        thresholds_file: The TOML file holding the check thresholds.
        frontend_directory: The directory holding the built React application.
        desktop_notifications_enabled: Whether failures raise desktop notifications.
    """

    model_config = SettingsConfigDict(
        env_prefix='SYSTEM_MONITOR_',
        env_file='.env',
        extra='ignore',
    )

    host: str = '0.0.0.0'
    port: int = 8090
    password_hash: str = ''
    session_secret: str = ''
    session_max_age_seconds: int = 43200
    unified_broker_interface_directory: Path = Path(
        '/home/pramod/Projects/unified_broker_interface'
    )
    thresholds_file: Path = Path('thresholds.toml')
    frontend_directory: Path = Path('frontend/dist')
    desktop_notifications_enabled: bool = True

    def require_security_values(self) -> None:
        """Checks that the password hash and session secret are set.

        Raises:
            ValueError: The password hash or the session secret is empty.
        """
        if not self.password_hash:
            raise ValueError('SYSTEM_MONITOR_PASSWORD_HASH is empty; run bin/set-password and add the hash to .env.')
        if not self.session_secret:
            raise ValueError('SYSTEM_MONITOR_SESSION_SECRET is empty; run bin/set-password and add the secret to .env.')

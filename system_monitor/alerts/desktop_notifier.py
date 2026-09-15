"""Shows notifications on the Linux desktop with notify-send.

Typical usage example:

  notifier = DesktopNotifier(CommandRunner(), enabled=True)
  notifier.send(notification)
"""

import logging
import subprocess

from system_monitor.alerts.alert_policy import Notification
from system_monitor.sources.command_runner import CommandRunner

_LOGGER = logging.getLogger(__name__)
_APPLICATION_NAME = 'System monitor'


class DesktopNotifier:
    """Sends notifications through notify-send."""

    def __init__(self, command_runner: CommandRunner, enabled: bool):
        """Creates the notifier.

        Args:
            command_runner (CommandRunner): Runs notify-send.
            enabled (bool): Whether to show notifications; when False they are only logged.
        """
        self.command_runner = command_runner
        self.enabled = enabled

    def send(self, notification: Notification) -> bool:
        """Shows one notification.

        Every notification is also written to the monitor's log, so it can be found later in the journal.

        Args:
            notification (Notification): The notification.

        Returns:
            bool: True when notify-send accepted it.
        """
        _LOGGER.warning('Alert (%s): %s: %s', notification.urgency, notification.title, notification.body.replace('\n', '; '))
        if not self.enabled:
            return False
        icon = 'dialog-warning' if notification.urgency == 'critical' else 'dialog-information'
        try:
            result = self.command_runner.run(
                [
                    'notify-send',
                    f'--app-name={_APPLICATION_NAME}',
                    f'--urgency={notification.urgency}',
                    f'--icon={icon}',
                    notification.title,
                    notification.body,
                ],
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            _LOGGER.warning('Could not run notify-send (reason: %r).', error)
            return False
        if result.return_code != 0:
            _LOGGER.warning('notify-send failed (exit %d): %s', result.return_code, result.standard_error.strip())
            return False
        return True

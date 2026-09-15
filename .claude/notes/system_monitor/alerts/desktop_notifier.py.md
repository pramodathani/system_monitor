# desktop_notifier.py

## Reaching the desktop from a service

`notify-send` talks to the notification daemon over the user's D-Bus session bus. The systemd user manager on this machine already carries `DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus` (checked with `systemctl --user show-environment` on 2026-09-15), so a user service inherits it and needs no extra environment. A direct test from the project on 2026-09-15 returned success.

If the monitor ever runs as a system service or on a machine without a graphical session, `notify-send` fails and the notifier logs a warning; the alert is still in the journal and on the dashboard.

## Every alert is logged

The notification is logged at WARNING before it is sent, so `journalctl --user -u system-monitor` is a history of every alert even when notifications are disabled or the desktop was locked.

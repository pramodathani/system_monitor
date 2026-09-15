# system-monitor.service

## A user unit, like UBI's

The monitor must call `systemctl --user` and `journalctl --user` for UBI's units, which only work inside the same user's systemd instance, and `notify-send` needs the user's D-Bus session bus. A user unit gets all three; a system unit would get none of them without extra configuration.

## `WantedBy=default.target`

UBI's targets use the same, so the monitor starts whenever the user manager starts. If the monitor should also run when nobody is logged in, enable lingering with `loginctl enable-linger pramod`; UBI's services would need that too.

## Restart policy

`Restart=always` with a ten-second delay. The most likely crash is a bad edit to `.env` or `thresholds.toml`, which fails at startup; the journal shows the `ValueError` with the setting's name every ten seconds until it is fixed.

## Not installed automatically

The service reads `SYSTEM_MONITOR_PASSWORD_HASH` from `.env`, which only the user can create with `bin/set-password`. Without it, startup stops with an instruction rather than serving an unprotected restart button.

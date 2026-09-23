# unit_controller.py

## The allow-list

A unit may be acted on only if all of these hold:

- the action is `start` or `restart`;
- the name ends in `.service` (timers are managed by systemd's schedule, and restarting a timer does not run its job);
- the exact name is a member of one of UBI's targets, as found by `UnitInventory`.

The name is compared exactly and passed to `systemctl` as a separate argument without a shell, so names such as `zerodha-instruments@websocket_quotes.service; rm -rf ~` are refused by the allow-list and could not be interpreted as shell syntax anyway. The test `test_perform_rejects_units_outside_inventory_and_timers` covers this.

## Starting a login job

`<broker>-login.service` is in the inventory, so the dashboard can start it to re-run a failed morning login. That performs a real Selenium login with the broker. The front end must warn about this in its confirmation dialog.

## Audit trail

Each action is logged through the `system_monitor.controls.unit_controller` logger, which ends up in the monitor's own journal (`journalctl --user -u system-monitor`), and the last fifty are kept in memory for the dashboard's "Recent actions" list. The browser's network address is recorded; there is only one account, so the address is the only thing that distinguishes devices.

# systemd_client.py

## `--timestamp=unix`

Without it, `systemctl show` prints times such as `Tue 2026-09-15 08:30:21 IST`, which would need locale-aware parsing. With it, the same property prints `@1789441221`. The option exists since systemd 251; this machine runs 259.

## One `show` call for every unit

Reading all 146 UBI units in one call took 0.24 s on 2026-09-15, so the services collector can run every five seconds without spawning 146 processes.

## Why `--no-block` on start and restart

A login unit is a oneshot that drives a real browser login with Selenium and can take minutes. Without `--no-block`, `systemctl start` waits until the oneshot finishes, which would hang the web request. With it, systemd queues the job and returns at once; the dashboard shows the result on the next services collection.

## Why only start and restart

`stop` on a UBI service ends a live feed or order-update stream with no automatic restart, which is the kind of mistake a dashboard button makes easy. The user asked for restart controls; stopping stays a deliberate terminal command.

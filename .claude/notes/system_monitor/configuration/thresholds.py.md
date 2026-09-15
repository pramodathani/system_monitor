# thresholds.py

## Where the starting values come from

- **Feed age 45 s warning:** UBI's own `STALE_SOCKET_SECONDS = 45.0` in `stock_brokers/instruments/ticks/utilities/sources.py`, the point at which UBI itself treats a broker socket as silent.
- **Stoxkart override (300 s / 900 s):** Stoxkart's quotes script is a REST poller that writes a tick only when the price changed, so a quiet instrument list can legitimately produce no ticks for minutes.
- **Stream caps:** from `docs/architecture/redis-keys.md` in UBI: about 100,000 for broker quote streams, 20,000 for broker order and position update streams, 200,000 for `unified:quotes:stream`, and 50,000 for the unified update streams. Streams are trimmed with approximate `MAXLEN`, so a lagging consumer group loses entries once its lag passes the cap. That is why the failure rule is a fraction of the cap rather than an absolute number.
- **Portfolio 60 s / 300 s:** UBI marks a broker `stale` in unified documents after 60 s (`STALE_SECONDS` in `bin/unified/positions`). Fyers is the slowest poller at 30 s for funds, which stays under 60 s.
- **Holdings 180 s / 600 s:** holdings are polled once a minute.
- **Reference data by 09:00:** `unified-instruments.timer` fires at 07:45 with up to 30 minutes of random delay, and the mapping observed on 2026-09-15 was written at 08:01:51.
- **Alerts:** two consecutive failures avoids alerting on a single slow Redis reply; ten minutes of cooldown stops a flapping check from notifying every few seconds.

## Why a `_SectionReader` rather than pydantic

The thresholds file is small and flat. A tiny reader that names the section and key in every error keeps the loading logic visible in one place, without a second validation framework's error formatting.

## Why `@staticmethod` on `_section`

It needs no instance or class state; the user's rules allow `@staticmethod` in that case rather than a module-level function.

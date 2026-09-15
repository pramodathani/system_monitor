# market_calendar.py

## Why read MongoDB rather than import UBI's calendar code

UBI has `stock_brokers/instruments/ticks/utilities/sessions.py` (`TradingCalendar`, `SessionGate`), but importing it would tie the monitor to UBI's Python environment and module layout. UBI already copies the same calendars into the `exchange_details` collection (see `unified_broker_interface/utilities/exchange_calendar.py`), with `trading_hours`, `holidays` and `special_sessions` per exchange, so the monitor reads that.

Note that UBI's `sessions.py` uses wider windows (opening at 09:00 for every segment) for accepting ticks. The monitor uses the real trading hours from `exchange_details`, and relies on the feeds' grace period after opening to cover pre-open silence.

## The built-in fallback

If MongoDB cannot be read at startup, feed checks still need to know roughly when markets trade, or every feed would be judged at night. The fallback is NSE equity 09:15–15:30 and MCX commodity 09:00–23:30 (23:55 during US standard time), with no holidays. On a holiday with MongoDB down, feeds would be wrongly judged; that is acceptable because MongoDB being down is itself a red data-store check.

## Rules encoded

- Weekends have no normal sessions.
- A holiday's `closed` is `all`, `morning` or `evening`; the latter two remove only the session of that name (commodity calendars).
- A special session is added on its date even on a weekend (Muhurat trading on Sunday 2026-11-08).
- An evening session with `closes_during_us_standard_time` uses that later close when New York is not on daylight saving time, matching the exchange's practice.

## Continuous open periods

`seconds_since_open` joins back-to-back sessions of the same calendar. Without that, at 17:05 the MCX evening session would look five minutes old and the feeds' grace period would hide a feed that had actually been silent all afternoon.

## Refresh timing

The collection changes only when someone runs `import-api-details --calendars-only`, so an hourly read is plenty. A failed read retries after a minute and keeps whatever was loaded before.

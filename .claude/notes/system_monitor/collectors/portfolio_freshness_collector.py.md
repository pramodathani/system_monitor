# portfolio_freshness_collector.py

## Two ways a broker records a read

- Orders and positions are merged hashes written by two scripts, so the polling script records its last successful read in a separate `...:polled_at` key (epoch seconds). Both keys expire at 06:00 India time.
- Trades, funds and holdings are replaced whole as `{timestamp, status, code, data}` documents, where `timestamp` is a local India time string. A document can be fresh but carry a failed status, which is why a fresh document with a status other than `success` is a warning.

## Why only datasets with a running service

Not every broker runs every script (Kotak has no user details service, Stoxkart no position persister). Checking for a key whose writer does not exist would be permanently red, so each check is created only when the script that writes it is in the inventory, which `UnitInventory.has_script` answers. The orders check therefore depends on `bin/<broker>/orders/api_order_details`, the trades check on `api_trade_details`, and the positions, funds and holdings checks on the scripts of those names under `bin/<broker>/portfolio/`.

## Unified documents

The combiners write `brokers: [{broker, status, as_of}]`. A combined document that is itself fresh but built without one broker's data is a warning naming that broker, so the combined view explains a broker-level failure rather than hiding it.

## Observed on the first live run

On 2026-09-15 at 15:15, Kotak positions and trades had not been read for 3 h 13 min, and the corresponding services had logged 15 errors each in 15 minutes, while the services themselves were running. This is the case the check exists for: a process that is up but not doing its job.

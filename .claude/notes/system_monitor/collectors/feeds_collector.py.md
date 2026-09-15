# feeds_collector.py

## Why the stream ID instead of `received_at` in the live hash

A Redis stream entry ID is `<milliseconds>-<sequence>`, so `last-generated-id` from `XINFO STREAM` is the time of the newest tick at the cost of one small command. Reading `received_at` would mean scanning the whole live hash every five seconds, and the hash keeps instruments that are no longer subscribed.

## Why learn each feed's exchanges

Measured on 2026-09-15: Groww, INDmoney and Wisdom Capital subscribe only to NSE instruments, while Zerodha, Dhan, Flattrade, Fyers, Kotak, Shoonya and Stoxkart mix NSE and MCX. Judging every feed against "any market open" would turn the three NSE-only feeds red from 15:30 to 23:30 every day. The `exchange` field of the ticks in `<subject>:quotes:live` says which markets a feed covers; `TickExchangeClassifier` turns each broker's spelling into a calendar. When nothing can be classified, every market counts, which errs towards alerting.

The live hash is not cleared at startup, so an instrument unsubscribed long ago still contributes its exchange. That can only make a feed be judged during more sessions, never fewer.

## Grace period

Brokers' sockets often stay quiet for a minute or two after 09:15 while the pre-open auction settles, and some feeds reconnect only after the session starts. A silent feed within `grace_after_open_seconds` of the continuous open period starting is idle rather than failed. A feed that is already ticking is judged normally.

## Observed on the first live run

At 15:17 on 2026-09-15 the NSE-only feeds had no tick since 15:15:13, while Zerodha and Flattrade still had NSE ticks 29 s old. Whether that was UBI or the brokers was not investigated; the collector reported it correctly as a warning.

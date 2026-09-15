# unified_broker_interface_configuration.py

## Why read UBI's `.env` instead of keeping our own copy

UBI's `.env` holds the MongoDB and TimescaleDB passwords that guard every broker's API key, secret and TOTP seed. A second copy in this project would be a second place to leak them and a second place to forget to update when they change. Reading the file directly with `dotenv_values` (which does not touch `os.environ`) keeps one source of truth.

The variable names mirror `utilities/configurations.py` in UBI: `UNIFIED_BROKER_INTERFACE_{REDIS,MONGODB,POSTGRES}_{HOST,PORT,DB,USERNAME,PASSWORD}` and the optional `UNIFIED_BROKER_INTERFACE_API_{HOST,PORT}`, which default to `127.0.0.1:8080` there as well.

## The REST API URL

Only `GET /api/` is ever called. It is UBI's unauthenticated greeting route. Every other route needs the application's single access token, and connecting to get one would log `tradingmachine` out.

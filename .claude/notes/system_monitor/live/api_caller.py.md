# api_caller.py

## Why the token is read from Redis rather than obtained

UBI allows exactly one token for the whole application. `POST /api/session/connect` mints a new one and invalidates the previous, so a monitor that connected would silently break `tradingmachine`, which holds the token in normal use. The project's rule against calling that endpoint is the reason this module exists in the shape it does.

Reading `last_login` field `unified_broker_interface` gives the token already in force. Sending it changes nothing: the API's `TokenStore` simply recognises it. When the stored token is missing or has expired, the call goes out without one and the API's own 401 is shown, because minting a replacement is a login's job.

## Why only catalogued endpoints can be called

The path always comes from `ApiCatalogue` and never from the request, so the browser cannot steer a call at an arbitrary address. Only GET endpoints are in the catalogue, which is what makes it impossible to reach `POST /api/orders/place`, `PUT /api/orders/modify` or `DELETE /api/orders/cancel` from the monitor. Those three place and change real money orders.

Query parameters are filtered against the endpoint's own declared list for the same reason, so an unexpected parameter is dropped rather than forwarded.

## Why the body is read in chunks

`GET /api/instruments/master` with `exchange=all` answers with every mapped instrument, and `GET /api/instruments/ticks` over a wide range answers with every stored tick. Either can run to hundreds of megabytes. The body is streamed and abandoned past four megabytes, and the answer says it was cut short, so a careless request costs a moment rather than the server's memory.

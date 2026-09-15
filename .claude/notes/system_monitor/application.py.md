# application.py

## One uvicorn worker

All state (check results, history, lockouts, recent actions) is held in memory by one process. A second worker would have its own empty state and its own collectors, doubling the load on UBI's Redis and showing different data depending on which worker answered.

## `create_web_application` separated from `build`

`build` connects the real sources. `create_web_application` only assembles middleware and routes from ready components, so the route tests can pass fakes and skip the lifespan that would start collectors against the real system.

## Lifespan

Startup refreshes the unit inventory before starting the collectors. Without that, the first run of every collector would see an empty inventory, and the log collector would advance its journal cursor past lines it discarded as "not a UBI unit".

## Quieting httpx

The REST API probe runs every fifteen seconds and `httpx` logs every request at INFO, which would add about 5,800 lines a day to the monitor's journal. Its logger is raised to WARNING.

## Logging format

The format has no timestamp because the journal adds one to every line.

# snapshot_routes.py

## Why server-sent events rather than WebSockets

Data flows one way, from server to browser; unit actions are ordinary POST requests. Server-sent events work over plain HTTP, reconnect automatically in the browser's `EventSource`, send the session cookie like any other request, and need no extra library on either side.

## Polling a version number

Collectors apply their outcomes on the event loop thread, and `MonitorState.version` increases with each one. The stream compares `(state version, controller version)` every two seconds and sends the whole snapshot when it changed. With ten collectors on intervals of five to thirty seconds, the version changes almost every check, so in practice a snapshot goes out every two seconds. At about 210 KB per snapshot (measured on 2026-09-15 with 420 checks) that is roughly 100 KB/s per open tab, which a home network handles easily.

## Keepalive

A comment line every fifteen seconds when nothing changed stops idle connections from being dropped by anything in between, and lets the browser notice a dead server.

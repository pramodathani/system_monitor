# timescaledb_health.py

## Why it opens its own connection

`PostgresProbe` connects, runs `SELECT 1` and disconnects, which answers reachability but nothing else. Rather than widen that class, this one repeats the small amount of connection code and runs the four statistics queries it needs. The project prefers a self-contained class per case to a shared parameterised one, and the duplication here is four lines of `psycopg2.connect`.

The connection is closed as soon as the reading is taken. The live view can be left open on a timer, and an idle connection held per page view would eat into `max_connections`, which stood at 100 while 24 connections were already open.

## Why the version string is shortened

`version()` returns the whole build string, including the compiler and the architecture: "PostgreSQL 18.6 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit". Only the first two words say anything a reader wants at a glance, and the TimescaleDB extension version is reported separately because that is the number that actually matters for the hypertables.

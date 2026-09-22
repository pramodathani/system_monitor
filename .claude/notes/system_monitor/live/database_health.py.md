# database_health.py

## Why "last reboot" needs two answers

Each store reports its own liveness differently. Redis and MongoDB give an uptime in seconds, PostgreSQL gives the moment `pg_postmaster_start_time` recorded, and neither tells you when the container around the process was started. A store restarted inside a container that kept running has a short uptime and an old container; a container recreated this morning has both fresh. Showing the store's start time and the container's separately is what makes the difference visible.

The two are converted into one shape here so that each store ends up carrying both a start time and an uptime, whichever it happened to report.

## Why Docker failing does not fail the reading

The stores answer for themselves. Docker adds the container's start time, its restart count and its own health check, all of which are useful and none of which are essential. A machine where `docker` is missing, slow or refusing still gets three complete store readings, and the page says plainly why the container details are absent.

## Why the containers are matched by compose service

The container is found by its `com.docker.compose.service` label rather than by its name. The name carries the project name and an instance number, so `unified_broker_interface-redis-1` would stop matching if the project were renamed or a second instance started. The service label is the stable part.

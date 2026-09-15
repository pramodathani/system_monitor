# settings.py

## Why `0.0.0.0:8090`

The user chose to reach the dashboard from other devices on the local network, so the server listens on every interface. Port 8080 is UBI's REST API and 8501 is its Streamlit test page; 8090 was free when the project started.

## Why the security values are checked separately

`Settings()` must be constructible without a password so that `bin/set-password` and the tests can use it. The web server calls `require_security_values()` before it starts, so a missing hash or secret stops the server with an instruction rather than serving an unprotected restart button.

## Session length

Twelve hours (43,200 s) covers a trading day from before the 08:15 login timer to after the 23:30 commodity close without a second login, while still expiring overnight.

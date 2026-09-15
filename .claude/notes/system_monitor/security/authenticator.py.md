# authenticator.py

## Why argon2

argon2 is deliberately slow and memory-hard, so a stolen `.env` hash cannot be brute-forced quickly. `argon2-cffi`'s default parameters take tens of milliseconds per check, which is fine for a login form and far too slow for guessing.

## Lockout

Five wrong passwords from one address within five minutes block that address until the oldest failure is five minutes old. The lockout is per address so that a misbehaving device does not lock the user out from their own laptop. It is in memory, so restarting the monitor clears it; that is acceptable for a home network, where the goal is to make online guessing impractical, not to withstand a determined attacker with physical access.

An invalid hash (for example a truncated line in `.env`) rejects every password rather than raising, so a configuration mistake shows as "Wrong password" instead of a server error that might be mistaken for an outage.

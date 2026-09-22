# view_catalogue.py

## Why the browser names a tab and never a key

A route that accepted a Redis key from the browser would let anyone who logged in read any key in UBI's Redis. That is a much wider capability than the live view needs, and it would turn a reading page into a general Redis console that nobody reviewed. Declaring the tabs here means the set of readable keys is fixed, is visible in one file, and changes only in a commit.

The chosen broker is checked the same way, against `UnitInventory.brokers()`, because the broker fills a placeholder in the key. Without that check, a broker name of `unified` or worse would build a key nobody intended.

## Why the unified session status tab looks empty

`unified:session:status` is written by `bin/unified/login`, and on this system that script has never run, so the key does not exist. The application token the REST API actually authenticates with lives in the `last_login` hash under the field `unified_broker_interface`, written by the REST API's own connect.

Both are shown. The session status tab is kept because it is the key the user asked for and its absence is itself worth seeing, and the application token tab is beside it so the page is not simply blank where the token should be.

## Why a broker's stored login has a tab

The reframed specification replaced it with `<broker>:session:status`, which carries the same status and token. The `last_login` field is kept as a tab of its own because the two can disagree: `session:status` is what that broker's login script last wrote, while `last_login` is what every process actually reads its token from. Seeing them side by side is how a stale token is spotted.

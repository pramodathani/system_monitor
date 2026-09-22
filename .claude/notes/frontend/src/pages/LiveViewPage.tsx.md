# LiveViewPage.tsx

## Why this page does not take the snapshot

Every other page receives `snapshot` and renders it. This one fetches for itself, because it shows stored values rather than checks, and because most of what it shows is far too large to put in a snapshot that is broadcast to every open browser every two seconds.

## Why documents refresh and tables do not

`unified:orders:orders` and the portfolio documents are rewritten every half second, so a document tab that did not re-read would be showing something already old. The instrument tables change once a day, at about 07:45, and run to half a million rows; re-reading one on a timer would cost Redis a walk for no new information. Documents therefore poll every five seconds with a pause control, and tables load when asked.

## Why the section tabs are buttons rather than routes

The page has four sections and, within two of them, a dozen tabs and a broker dropdown. Putting all of that in the URL would mean a router shape that no other page needs, and the state is not worth bookmarking. The trade-off is that a reload returns to the databases section.

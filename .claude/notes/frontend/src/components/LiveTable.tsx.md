# LiveTable.tsx

## Why nothing loads until asked

Opening the Instruments master tab on a whim should not make Redis walk a hash of half a million fields. The tab shows what the table is and how many rows it holds, and reads the first page only when the button is pressed.

## Why there is a "previous" button but no page numbers

Redis hands back a cursor, not an offset, so the server can continue a walk but cannot jump. The component keeps every cursor it has been given in a ref, which is enough to step back one page at a time. It is a ref rather than state because pushing a cursor must not by itself cause a render.

## Why a search replaces the page rather than filtering it

Searching walks the whole hash on the server, so its results have nothing to do with the page currently shown and no cursor of its own. The controls therefore hide "previous" and "next" while a search is on screen, and "Back to start" is how you leave it.

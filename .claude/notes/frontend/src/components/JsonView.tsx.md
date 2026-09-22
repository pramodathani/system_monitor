# JsonView.tsx

## Why a tree rather than formatted text

`JSON.stringify(value, null, 2)` in a `<pre>` would have been a tenth of the code. It reads badly for the documents this page actually shows: `unified:details:exchanges` is seventeen kilobytes and `unified:user:details` carries ten brokers' profiles. A tree that folds away the branches nobody is looking at is what makes those readable.

Branches two levels deep are open to begin with, which shows the shape of a document without unfolding every holding and every order.

## Why an array of similar objects is offered as a table

Holdings, positions, orders and trades are all lists of objects with the same fields. As a tree each one becomes a numbered branch that has to be opened separately, and comparing two rows means opening both. As a table they are one row each and can be read down a column.

The test for "similar" is strict: every item must be a plain object and every item must have exactly the same field names. A table that silently dropped a field present on only some rows would be quietly wrong, which is worse than a tree.

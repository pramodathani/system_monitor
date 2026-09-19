# serviceOrder.ts

## Why the services have a fixed order

The services page lists each broker's services in the order the user reads them, which follows the flow of work: login profile first, then orders and their updates and persistence, then trades, holdings, positions and funds, then market data (historical prices, quotes, persisted ticks). Alphabetical order scattered related services across the table.

## Two naming shapes

Most services are instances of the broker's template unit, named `<broker>@<role>.service`, such as `dhan@orders.service`. The historical prices worker is a separate unit named `<broker>-historical-prices.service`. `ServiceOrder.role` strips either prefix so both shapes match the list.

## Services that are not in the list

Services not in the list, such as `details` on `unified`, go after every listed service, alphabetically among themselves. A new service therefore still appears, just at the bottom, until it is added to `ROLE_ORDER`.

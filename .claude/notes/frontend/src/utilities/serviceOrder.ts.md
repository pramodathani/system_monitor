# serviceOrder.ts

## Why the services have a fixed order

The services page lists each broker's services in the order the user reads them, which follows the flow of work: the account profile first, then orders, their live updates and their persistence, then trades, holdings, positions and funds, then market data (historical prices, quotes, persisted ticks). Alphabetical order scattered related services across the table.

## Two naming shapes

UBI groups each broker's scripts into folders by subject and runs each folder through a systemd template named after it, so most services are named `<broker>-<folder>@<script>.service`, such as `dhan-orders@api_order_details.service`. The historical prices worker is a plain unit named `<broker>-historical-prices.service`. Both shapes begin `<broker>-`, so `ServiceOrder.role` strips that one prefix and the rest of the name is the role: `orders@api_order_details` or `historical-prices`.

Before UBI's 2026-09-22 rename the first shape was `<broker>@<role>.service`, so `role` tried an `@` prefix before a `-` one. That first attempt now matches nothing and has been removed, and every entry in `ROLE_ORDER` was rewritten: `orders` became `orders@api_order_details`, `order_updates` became `orders@websocket_order_details`, `persist_orders` became `orders@store_orders_to_db`, `trades` became `orders@api_trade_details`, `holdings`, `positions` and `funds` gained a `portfolio@` prefix, `persist_positions` became `portfolio@store_positions_to_db`, `quotes` became `instruments@websocket_quotes`, `persist_ticks` became `instruments@store_quotes_to_db`, and `user-profile` became `user@details`.

## Services that are not in the list

Services not in the list, such as `unified-rest-api` or the `unified_details` cache writers, go after every listed service, alphabetically among themselves. A new service therefore still appears, just at the bottom, until it is added to `ROLE_ORDER`.

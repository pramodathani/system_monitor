import type { Check } from '../api/types';

const ROLE_ORDER: string[] = [
  'user@details',
  'orders@api_order_details',
  'orders@websocket_order_details',
  'orders@store_orders_to_db',
  'orders@api_trade_details',
  'portfolio@holdings',
  'portfolio@positions',
  'portfolio@store_positions_to_db',
  'portfolio@funds',
  'historical-prices',
  'instruments@websocket_quotes',
  'instruments@store_quotes_to_db',
];

/** Puts one broker's services in the order a person reads them. */
export class ServiceOrder {
  readonly subject: string;

  /**
   * Creates the ordering for one broker.
   * @param subject The broker name, such as "dhan", or "unified".
   */
  constructor(subject: string) {
    this.subject = subject;
  }

  /**
   * Finds a service's role, the part of its name after the broker.
   * @param check The service check, named like "dhan-orders@api_order_details" or "dhan-historical-prices".
   * @returns The role, such as "orders@api_order_details" or "historical-prices".
   */
  role(check: Check): string {
    const name = check.name.replace(/\.service$/, '');
    const prefix = `${this.subject}-`;
    if (name.startsWith(prefix)) {
      return name.slice(prefix.length);
    }
    return name;
  }

  /**
   * Ranks a service by its role; roles missing from the list rank after every listed one.
   * @param check The service check.
   * @returns The rank, lower first.
   */
  rank(check: Check): number {
    const position = ROLE_ORDER.indexOf(this.role(check));
    if (position === -1) {
      return ROLE_ORDER.length;
    }
    return position;
  }

  /**
   * Sorts services by role, and alphabetically among services of equal rank.
   * @param checks The service checks of this broker.
   * @returns A new, sorted list.
   */
  sort(checks: Check[]): Check[] {
    const sorted = [...checks];
    sorted.sort((first, second) => {
      const byRank = this.rank(first) - this.rank(second);
      if (byRank !== 0) {
        return byRank;
      }
      return first.name.localeCompare(second.name);
    });
    return sorted;
  }
}

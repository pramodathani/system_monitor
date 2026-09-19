import type { Check } from '../api/types';

const ROLE_ORDER: string[] = [
  'user-profile',
  'orders',
  'order_updates',
  'persist_orders',
  'trades',
  'holdings',
  'positions',
  'persist_positions',
  'funds',
  'historical-prices',
  'quotes',
  'persist_ticks',
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
   * @param check The service check, named like "dhan@orders" or "dhan-historical-prices".
   * @returns The role, such as "orders" or "historical-prices".
   */
  role(check: Check): string {
    const name = check.name.replace(/\.service$/, '');
    for (const separator of ['@', '-']) {
      const prefix = `${this.subject}${separator}`;
      if (name.startsWith(prefix)) {
        return name.slice(prefix.length);
      }
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

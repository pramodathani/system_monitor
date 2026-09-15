import type { Check, CheckStatus } from '../api/types';

const SEVERITY: Record<CheckStatus, number> = {
  failure: 4,
  warning: 3,
  unknown: 2,
  ok: 1,
  idle: 0,
};

const STATUS_LABELS: Record<CheckStatus, string> = {
  ok: 'OK',
  warning: 'Warning',
  failure: 'Failing',
  idle: 'Idle',
  unknown: 'Unknown',
};

/** Groups and ranks the checks of one snapshot. */
export class CheckIndex {
  readonly checks: Check[];

  /**
   * Creates the index.
   * @param checks Every check in the snapshot.
   */
  constructor(checks: Check[]) {
    this.checks = checks;
  }

  /**
   * Ranks a status so the worse one compares higher.
   * @param status The status.
   * @returns The severity rank.
   */
  static severity(status: CheckStatus): number {
    return SEVERITY[status];
  }

  /**
   * Names a status for people.
   * @param status The status.
   * @returns The label, such as "Failing".
   */
  static label(status: CheckStatus): string {
    return STATUS_LABELS[status];
  }

  /**
   * Finds the worst status among some checks.
   * @param checks The checks.
   * @returns The worst status, or null when there are none.
   */
  static worstStatus(checks: Check[]): CheckStatus | null {
    let worst: CheckStatus | null = null;
    for (const check of checks) {
      if (worst === null || SEVERITY[check.status] > SEVERITY[worst]) {
        worst = check.status;
      }
    }
    return worst;
  }

  /**
   * Keeps the checks of some areas.
   * @param areas The areas to keep.
   * @returns The matching checks.
   */
  inAreas(areas: string[]): Check[] {
    const matching: Check[] = [];
    for (const check of this.checks) {
      if (areas.includes(check.area)) {
        matching.push(check);
      }
    }
    return matching;
  }

  /**
   * Keeps the checks of some areas for one subject.
   * @param subject The broker name, "unified" or "platform".
   * @param areas The areas to keep.
   * @returns The matching checks.
   */
  forSubject(subject: string, areas: string[]): Check[] {
    const matching: Check[] = [];
    for (const check of this.inAreas(areas)) {
      if (check.subject === subject) {
        matching.push(check);
      }
    }
    return matching;
  }

  /**
   * Lists the subjects, brokers alphabetically followed by "unified".
   * @returns The subjects that have at least one check, excluding "platform" and "monitor".
   */
  subjects(): string[] {
    const brokers = new Set<string>();
    let hasUnified = false;
    for (const check of this.checks) {
      if (check.subject === 'unified') {
        hasUnified = true;
      } else if (check.subject !== 'platform' && check.subject !== 'monitor') {
        brokers.add(check.subject);
      }
    }
    const ordered = Array.from(brokers).sort();
    if (hasUnified) {
      ordered.push('unified');
    }
    return ordered;
  }

  /**
   * Lists checks that need attention, worst first and longest-standing first within a status.
   * @returns The failing, warning and unknown checks.
   */
  problems(): Check[] {
    const problems: Check[] = [];
    for (const check of this.checks) {
      if (check.status === 'failure' || check.status === 'warning' || check.status === 'unknown') {
        problems.push(check);
      }
    }
    problems.sort((first, second) => {
      const bySeverity = SEVERITY[second.status] - SEVERITY[first.status];
      if (bySeverity !== 0) {
        return bySeverity;
      }
      return first.status_since - second.status_since;
    });
    return problems;
  }

  /**
   * Counts checks per status.
   * @returns The count for each status.
   */
  countByStatus(): Record<CheckStatus, number> {
    const counts: Record<CheckStatus, number> = {
      ok: 0,
      warning: 0,
      failure: 0,
      idle: 0,
      unknown: 0,
    };
    for (const check of this.checks) {
      counts[check.status] += 1;
    }
    return counts;
  }

  /**
   * Finds one check by its id.
   * @param checkId The check id.
   * @returns The check, or undefined.
   */
  find(checkId: string): Check | undefined {
    return this.checks.find((check) => check.check_id === checkId);
  }
}

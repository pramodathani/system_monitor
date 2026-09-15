/** How healthy a checked thing is, as judged by the server. */
export type CheckStatus = 'ok' | 'warning' | 'failure' | 'idle' | 'unknown';

/** One check's latest judgement with its times and history. */
export interface Check {
  check_id: string;
  area: string;
  subject: string;
  name: string;
  status: CheckStatus;
  message: string;
  value: number | null;
  details: Record<string, unknown>;
  status_since: number;
  observed_at: number;
  collector: string;
  history?: Array<[number, number]>;
}

/** The last run of one collector. */
export interface CollectorRun {
  name: string;
  started_at: number;
  duration_seconds: number;
  error: string | null;
  check_count: number;
}

/** A start or restart requested from the dashboard. */
export interface UnitAction {
  requested_at: number;
  unit: string;
  action: string;
  address: string;
  succeeded: boolean;
  message: string;
}

/** A desktop notification the server sent. */
export interface AlertNotification {
  title: string;
  body: string;
  urgency: string;
  created_at: number;
}

/** A trading session open right now. */
export interface OpenSession {
  exchange: string;
  calendar: string;
  name: string;
  closes_at: number;
}

/** The whole document the server streams. */
export interface Snapshot {
  version: number;
  generated_at: number;
  checks: Check[];
  collectors: CollectorRun[];
  actions: UnitAction[];
  notifications: AlertNotification[];
  open_sessions: OpenSession[];
  calendar_source: string;
}

/** One journal line from the log stream. */
export interface LogLine {
  timestamp: number;
  level: string;
  text: string;
  continuation: boolean;
}

import type { Snapshot, UnitAction } from './types';

const REQUESTED_WITH_HEADER = 'X-Requested-With';
const REQUESTED_WITH_VALUE = 'system-monitor';

/** An error answer from the server, carrying its status code and message. */
export class ApiError extends Error {
  readonly statusCode: number;

  /**
   * Creates the error.
   * @param statusCode The HTTP status code.
   * @param message The server's explanation.
   */
  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

/** Calls the monitor's own server. */
export class ApiClient {
  /**
   * Asks whether this browser is logged in.
   * @returns True when the session is logged in.
   */
  async isLoggedIn(): Promise<boolean> {
    const response = await fetch('/api/auth/session', {
      credentials: 'same-origin',
    });
    const body = await this.readJson(response);
    return body.authenticated === true;
  }

  /**
   * Logs in with the dashboard password.
   * @param password The password typed in.
   * @throws ApiError when the password is wrong or the address is locked out.
   */
  async logIn(password: string): Promise<void> {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
      body: JSON.stringify({
        password,
      }),
    });
    await this.readJson(response);
  }

  /** Logs out. */
  async logOut(): Promise<void> {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    await this.readJson(response);
  }

  /**
   * Fetches the current snapshot once.
   * @returns The snapshot.
   */
  async fetchSnapshot(): Promise<Snapshot> {
    const response = await fetch('/api/snapshot', {
      credentials: 'same-origin',
    });
    return (await this.readJson(response)) as unknown as Snapshot;
  }

  /**
   * Starts or restarts one of UBI's services.
   * @param unitName The exact unit name.
   * @param action "start" or "restart".
   * @returns The recorded action.
   * @throws ApiError when the server refuses or systemctl fails.
   */
  async performUnitAction(unitName: string, action: 'start' | 'restart'): Promise<UnitAction> {
    const response = await fetch(`/api/units/${encodeURIComponent(unitName)}/${action}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        [REQUESTED_WITH_HEADER]: REQUESTED_WITH_VALUE,
      },
    });
    return (await this.readJson(response)) as unknown as UnitAction;
  }

  /**
   * The address of the event stream for one unit's journal.
   * @param unitName The exact unit name.
   * @param lineCount How many earlier lines to send first.
   * @returns The URL.
   */
  logStreamUrl(unitName: string, lineCount: number): string {
    return `/api/logs/${encodeURIComponent(unitName)}/events?lines=${lineCount}`;
  }

  /**
   * Reads a JSON answer, turning an error status into an ApiError.
   * @param response The fetch response.
   * @returns The parsed body.
   * @throws ApiError when the status is not successful.
   */
  private async readJson(response: Response): Promise<Record<string, unknown>> {
    let body: Record<string, unknown> = {};
    try {
      body = await response.json();
    } catch {
      body = {};
    }
    if (!response.ok) {
      const detail = typeof body.detail === 'string' ? body.detail : response.statusText;
      throw new ApiError(response.status, detail);
    }
    return body;
  }
}

export const apiClient = new ApiClient();

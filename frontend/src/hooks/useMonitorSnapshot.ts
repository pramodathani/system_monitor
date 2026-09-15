import { useEffect, useState } from 'react';

import { apiClient } from '../api/apiClient';
import type { Snapshot } from '../api/types';

const RECONNECT_DELAY_MILLISECONDS = 3000;

/** The live snapshot and whether its stream is connected. */
export interface SnapshotConnection {
  snapshot: Snapshot | null;
  connected: boolean;
}

/**
 * Follows the server's snapshot stream, reconnecting after failures.
 * @param onLoggedOut Called when the stream fails because the session ended.
 * @returns The latest snapshot and the connection state.
 */
export function useMonitorSnapshot(onLoggedOut: () => void): SnapshotConnection {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const source = new EventSource('/api/events');
    let reconnectTimer: number | undefined;
    let stopped = false;

    source.addEventListener('snapshot', (event) => {
      const message = event as MessageEvent<string>;
      setSnapshot(JSON.parse(message.data) as Snapshot);
      setConnected(true);
    });
    source.addEventListener('open', () => {
      setConnected(true);
    });
    source.addEventListener('error', () => {
      setConnected(false);
      if (source.readyState !== EventSource.CLOSED || stopped) {
        return;
      }
      apiClient
        .isLoggedIn()
        .then((loggedIn) => {
          if (stopped) {
            return;
          }
          if (!loggedIn) {
            onLoggedOut();
            return;
          }
          reconnectTimer = window.setTimeout(() => setAttempt((previous) => previous + 1), RECONNECT_DELAY_MILLISECONDS);
        })
        .catch(() => {
          if (!stopped) {
            reconnectTimer = window.setTimeout(() => setAttempt((previous) => previous + 1), RECONNECT_DELAY_MILLISECONDS);
          }
        });
    });

    return () => {
      stopped = true;
      window.clearTimeout(reconnectTimer);
      source.close();
    };
  }, [attempt, onLoggedOut]);

  return {
    snapshot,
    connected,
  };
}

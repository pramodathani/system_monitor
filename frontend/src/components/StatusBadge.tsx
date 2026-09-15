import type { CheckStatus } from '../api/types';
import { CheckIndex } from '../utilities/checkIndex';

/** Props for StatusIcon. */
interface StatusIconProps {
  status: CheckStatus;
}

/**
 * A small shape that differs per status, so status never relies on colour alone.
 * @param props The status to draw.
 * @returns The icon.
 */
export function StatusIcon(props: StatusIconProps) {
  const { status } = props;
  return (
    <svg className={`status-icon status-icon-${status}`} viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      {status === 'ok' && (
        <>
          <circle cx="8" cy="8" r="7" />
          <path d="M4.8 8.2 7 10.4l4.2-4.6" className="status-icon-mark" />
        </>
      )}
      {status === 'warning' && (
        <>
          <path d="M8 1.5 15 14H1z" />
          <path d="M8 6v3.6M8 11.6v.2" className="status-icon-mark" />
        </>
      )}
      {status === 'failure' && (
        <>
          <path d="M5.1 1h5.8L15 5.1v5.8L10.9 15H5.1L1 10.9V5.1z" />
          <path d="m5.6 5.6 4.8 4.8m0-4.8-4.8 4.8" className="status-icon-mark" />
        </>
      )}
      {status === 'idle' && (
        <>
          <circle cx="8" cy="8" r="6.5" className="status-icon-hollow" />
          <path d="M5 8h6" className="status-icon-mark-ink" />
        </>
      )}
      {status === 'unknown' && (
        <>
          <circle cx="8" cy="8" r="6.5" className="status-icon-hollow" />
          <path d="M6.2 6.2a1.9 1.9 0 1 1 2.6 1.7c-.5.3-.8.6-.8 1.3M8 11.4v.2" className="status-icon-mark-ink" />
        </>
      )}
    </svg>
  );
}

/** Props for StatusBadge. */
interface StatusBadgeProps {
  status: CheckStatus;
  label?: string;
}

/**
 * A status icon followed by its label in ordinary text colour.
 * @param props The status and an optional label replacing the default one.
 * @returns The badge.
 */
export function StatusBadge(props: StatusBadgeProps) {
  const { status, label } = props;
  return (
    <span className="status-badge">
      <StatusIcon status={status} />
      <span>{label ?? CheckIndex.label(status)}</span>
    </span>
  );
}

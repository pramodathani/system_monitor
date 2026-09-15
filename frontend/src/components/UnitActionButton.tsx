import { useEffect, useRef, useState } from 'react';

import { ApiError, apiClient } from '../api/apiClient';

/** Props for UnitActionButton. */
interface UnitActionButtonProps {
  unitName: string;
  action: 'start' | 'restart';
  buttonLabel: string;
  warning?: string;
  disabled?: boolean;
}

/**
 * A button that asks for confirmation and then starts or restarts a service.
 * @param props The unit, the action, the button text, an optional extra warning, and whether it is disabled.
 * @returns The button with its confirmation dialog and result message.
 */
export function UnitActionButton(props: UnitActionButtonProps) {
  const { unitName, action, buttonLabel, warning, disabled } = props;
  const dialogReference = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const dialog = dialogReference.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const confirm = async () => {
    setBusy(true);
    try {
      const recorded = await apiClient.performUnitAction(unitName, action);
      setResult({
        ok: true,
        text: recorded.message,
      });
    } catch (error) {
      const text = error instanceof ApiError ? error.message : 'The request did not reach the server.';
      setResult({
        ok: false,
        text,
      });
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  const verb = action === 'restart' ? 'Restart' : 'Start';

  return (
    <span className="unit-action">
      <button type="button" className="button" disabled={disabled || busy} onClick={() => setOpen(true)}>
        {busy ? 'Working…' : buttonLabel}
      </button>
      {result && <span className={result.ok ? 'action-result' : 'action-result action-result-error'}>{result.text}</span>}
      <dialog ref={dialogReference} className="dialog" onClose={() => setOpen(false)}>
        <h2>
          {verb} {unitName}?
        </h2>
        <p>
          systemd will {action} this user service on the monitored machine. The request is recorded with your network address.
        </p>
        {warning && <p className="dialog-warning">{warning}</p>}
        <div className="dialog-buttons">
          <button type="button" className="button" onClick={() => setOpen(false)} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="button button-primary" onClick={confirm} disabled={busy}>
            {verb}
          </button>
        </div>
      </dialog>
    </span>
  );
}

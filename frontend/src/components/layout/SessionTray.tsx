import { SessionListShell } from '@/components/session/SessionList';

interface SessionTrayProps {
  open: boolean;
}

export function SessionTray({ open }: SessionTrayProps) {
  return (
    <aside className={`session-tray${open ? ' is-open' : ''}`}>
      <div className="session-tray-inner">
        <SessionListShell />
      </div>
    </aside>
  );
}

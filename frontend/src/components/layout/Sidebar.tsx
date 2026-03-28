import { useState, useEffect } from 'react';
import { useUiStore } from '@/store/uiStore';
import { SessionListShell } from '@/components/session/SessionList';
import { apiGet } from '@/api/client';

export function Sidebar() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const [version, setVersion] = useState('');

  useEffect(() => {
    apiGet<{ config: { version?: string } }>('/api/config')
      .then((data) => setVersion(data.config?.version ?? ''))
      .catch(() => {});
  }, []);

  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-mark" aria-hidden="true">
          <img src="/logo-claw.png" alt="" className="brand-mark-image" />
        </div>
        <h1>EurekaLab {version && <span className="version-pill">v{version}</span>}</h1>
      </div>

      <nav className="nav-stack" aria-label="Primary">
        <button
          className={`nav-item${activeView === 'workspace' ? ' is-active' : ''}`}
          data-view-target="workspace"
          onClick={() => setActiveView('workspace')}
        >
          Research
        </button>
        <button
          className={`nav-item${activeView === 'skills' ? ' is-active' : ''}`}
          data-view-target="skills"
          onClick={() => setActiveView('skills')}
        >
          Skills
        </button>
      </nav>

      <SessionListShell />

      <hr className="nav-divider sidebar-bottom-divider" />
      <button
        className={`nav-item nav-item--settings${activeView === 'systems' ? ' is-active' : ''}`}
        data-view-target="systems"
        onClick={() => setActiveView('systems')}
      >
        Settings
      </button>
      <a
        className="nav-item nav-item--docs"
        href="https://github.com/Lvigentini/EurekaLab/tree/main/docs"
        target="_blank"
        rel="noopener noreferrer"
      >
        Docs ↗
      </a>
    </aside>
  );
}

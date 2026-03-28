import { useEffect, useState } from 'react';
import { useUiStore } from '@/store/uiStore';
import { useSkillStore } from '@/store/skillStore';
import { usePolling } from '@/hooks/usePolling';
import { apiGet } from '@/api/client';
import { Header } from '@/components/layout/Header';
import { SessionTray } from '@/components/layout/SessionTray';
import { FlashOverlay } from '@/components/layout/FlashOverlay';
import { NewSessionForm } from '@/components/session/NewSessionForm';
import { SessionDetailPane } from '@/components/session/SessionDetailPane';
import { SkillsView } from '@/components/skills/SkillsView';
import { ConfigView } from '@/components/config/ConfigView';
import { DocsView } from '@/components/docs/DocsView';
import { AgentDrawer } from '@/components/agent/AgentDrawer';
import { useSessionStore } from '@/store/sessionStore';
import type { Skill } from '@/types';

interface SkillsResponse {
  skills: Skill[];
}

const TRAY_KEY = 'eurekalab_tray_open';

export function App() {
  const activeView = useUiStore((s) => s.activeView);
  const setActiveView = useUiStore((s) => s.setActiveView);
  const currentRun = useSessionStore((s) => s.currentRun());
  const setAvailableSkills = useSkillStore((s) => s.setAvailableSkills);

  const [trayOpen, setTrayOpen] = useState(() => {
    try { return localStorage.getItem(TRAY_KEY) !== 'false'; } catch { return true; }
  });

  const toggleTray = () => {
    setTrayOpen((prev) => {
      const next = !prev;
      try { localStorage.setItem(TRAY_KEY, String(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const { restartFast } = usePolling();

  useEffect(() => {
    const hasPersistedView = localStorage.getItem('eurekalab_ui');
    if (!hasPersistedView) {
      setActiveView('workspace');
    }
  }, [setActiveView]);

  useEffect(() => {
    void (async () => {
      try {
        const data = await apiGet<SkillsResponse>('/api/skills');
        setAvailableSkills(data.skills ?? []);
      } catch { /* silently ignore */ }
    })();
  }, [setAvailableSkills]);

  const isWorkspaceView = activeView === 'workspace';

  return (
    <div className="app-shell">
      <Header trayOpen={trayOpen} onToggleTray={toggleTray} />

      <SessionTray open={trayOpen} />

      <main className="main-shell">
        <section className={`view${activeView === 'workspace' ? ' is-visible' : ''}`} data-view="workspace">
          {isWorkspaceView && (
            currentRun
              ? <SessionDetailPane run={currentRun} onRestartFast={restartFast} />
              : <NewSessionForm />
          )}
        </section>

        <section className={`view${activeView === 'skills' ? ' is-visible' : ''}`} data-view="skills">
          {activeView === 'skills' && <SkillsView />}
        </section>

        <section className={`view${activeView === 'systems' ? ' is-visible' : ''}`} data-view="systems">
          {activeView === 'systems' && <ConfigView />}
        </section>

        <section className={`view${activeView === 'docs' ? ' is-visible' : ''}`} data-view="docs">
          {activeView === 'docs' && <DocsView />}
        </section>

        {/* Guide button removed — docs are accessible from header nav */}
      </main>

      <AgentDrawer />
      <FlashOverlay />
    </div>
  );
}

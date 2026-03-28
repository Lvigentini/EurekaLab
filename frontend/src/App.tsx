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
import { OnboardingView } from '@/components/onboarding/OnboardingView';
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
  const setCurrentWizardStep = useUiStore((s) => s.setCurrentWizardStep);
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
      if (localStorage.getItem('eurekalab_tutorial_skipped') === '1') {
        setActiveView('workspace');
      } else {
        setActiveView('onboarding');
      }
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

  const handleGuideClick = () => {
    localStorage.removeItem('eurekalab_tutorial_skipped');
    setCurrentWizardStep(0);
    setActiveView('onboarding');
  };

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

        <section className={`view${activeView === 'onboarding' ? ' is-visible' : ''}`} data-view="onboarding">
          {activeView === 'onboarding' && <OnboardingView />}
        </section>

        <section className={`view${activeView === 'systems' ? ' is-visible' : ''}`} data-view="systems">
          {activeView === 'systems' && <ConfigView />}
        </section>

        <section className={`view${activeView === 'docs' ? ' is-visible' : ''}`} data-view="docs">
          {activeView === 'docs' && <DocsView />}
        </section>

        <button
          className="tutorial-btn"
          title="Setup guide &amp; tutorials"
          aria-label="Open setup guide"
          onClick={handleGuideClick}
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>Guide</span>
        </button>
      </main>

      <AgentDrawer />
      <FlashOverlay />
    </div>
  );
}

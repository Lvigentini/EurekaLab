import { create } from 'zustand';

type ActiveView = 'workspace' | 'skills' | 'systems' | 'docs';
type ActiveWsTab = 'live' | 'proof' | 'paper' | 'logs' | 'history';

const STORAGE_KEY = 'eurekalab_ui';

function loadPersistedUi(): { activeView: ActiveView; activeWsTab: ActiveWsTab } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      const validViews: ActiveView[] = ['workspace', 'skills', 'systems', 'docs'];
      const validTabs: ActiveWsTab[] = ['live', 'proof', 'paper', 'logs', 'history'];
      return {
        activeView: validViews.includes(parsed.activeView) ? parsed.activeView : 'workspace',
        activeWsTab: validTabs.includes(parsed.activeWsTab) ? parsed.activeWsTab : 'live',
      };
    }
  } catch { /* ignore */ }
  return { activeView: 'workspace', activeWsTab: 'live' };
}

function persistUi(view: ActiveView, tab: ActiveWsTab) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ activeView: view, activeWsTab: tab })); } catch { /* ignore */ }
}

interface UiState {
  activeView: ActiveView;
  activeWsTab: ActiveWsTab;
  openAgentDrawerRole: string | null;
  isFlashing: boolean;

  setActiveView: (view: ActiveView) => void;
  setActiveWsTab: (tab: ActiveWsTab) => void;
  setOpenAgentDrawerRole: (role: string | null) => void;
  flashTransitionTo: (view: ActiveView) => void;
}

const initial = loadPersistedUi();

export const useUiStore = create<UiState>((set, get) => ({
  activeView: initial.activeView,
  activeWsTab: initial.activeWsTab,
  openAgentDrawerRole: null,
  isFlashing: false,

  setActiveView: (view) => { set({ activeView: view }); persistUi(view, get().activeWsTab); },
  setActiveWsTab: (tab) => { set({ activeWsTab: tab }); persistUi(get().activeView, tab); },
  setOpenAgentDrawerRole: (role) => set({ openAgentDrawerRole: role }),

  flashTransitionTo: (view) => {
    set({ isFlashing: true });
    setTimeout(() => {
      set({ activeView: view, isFlashing: false });
    }, 90);
    const { setActiveView } = get();
    setActiveView(view);
  },
}));

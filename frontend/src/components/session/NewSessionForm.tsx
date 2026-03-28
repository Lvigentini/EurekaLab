import { useState } from 'react';
import { useSessionStore } from '@/store/sessionStore';
import { useSkillStore } from '@/store/skillStore';
import { useUiStore } from '@/store/uiStore';
import { apiPost } from '@/api/client';
import { humanize } from '@/lib/formatters';
import type { SessionRun } from '@/types';

const MODES = [
  {
    key: 'detailed',
    icon: '📐',
    label: 'Prove / Formalize',
    desc: 'State a claim and build a rigorous argument',
    hint: 'Best when you have a specific mathematical statement or conjecture to prove. EurekaLab will search the literature, formalize the claim, and construct a step-by-step proof.',
    promptLabel: 'Conjecture or claim to investigate',
    promptPlaceholder: 'e.g. The sample complexity of transformers is O(L·d·log(d)/ε²)',
    requirePrompt: true,
    requireDomain: false,
    showPaperIds: false,
    showBib: false,
    showDraft: false,
    showZotero: false,
  },
  {
    key: 'exploration',
    icon: '🔭',
    label: 'Explore',
    desc: 'Survey a domain and discover open problems',
    hint: 'Enter a research topic and EurekaLab will map the field — finding key papers, identifying trends, and highlighting open problems. Great for getting started in a new area.',
    promptLabel: 'Guiding question (optional)',
    promptPlaceholder: 'e.g. What are the main approaches to neural program synthesis?',
    requirePrompt: false,
    requireDomain: true,
    showPaperIds: false,
    showBib: false,
    showDraft: false,
    showZotero: false,
  },
  {
    key: 'reference',
    icon: '📚',
    label: 'From Papers',
    desc: 'Start from specific papers and find gaps',
    hint: 'Provide arXiv or Semantic Scholar IDs of papers you know. EurekaLab will analyze them, find related work, and identify research gaps you could address.',
    promptLabel: 'Research focus (optional)',
    promptPlaceholder: 'e.g. Find gaps in sparse attention theory, or leave blank to auto-detect',
    requirePrompt: false,
    requireDomain: true,
    showPaperIds: true,
    showBib: false,
    showDraft: false,
    showZotero: false,
  },
  {
    key: 'from_bib',
    icon: '📑',
    label: 'From .bib',
    desc: 'Start from your bibliography + local PDFs',
    hint: 'Paste a BibTeX file from your existing research. If you have PDFs locally, point to the directory and EurekaLab will extract full text for deeper analysis.',
    promptLabel: 'Research focus (optional)',
    promptPlaceholder: 'e.g. Strengthen the regret analysis section',
    requirePrompt: false,
    requireDomain: true,
    showPaperIds: false,
    showBib: true,
    showDraft: false,
    showZotero: false,
  },
  {
    key: 'from_draft',
    icon: '✏️',
    label: 'From Draft',
    desc: 'Start from a draft paper with instructions',
    hint: 'Paste your work-in-progress paper and tell EurekaLab what to do — strengthen theory, find missing references, extend results, or write a competing analysis.',
    promptLabel: 'Instruction for EurekaLab',
    promptPlaceholder: 'e.g. Help me strengthen the theory section and find related work I missed',
    requirePrompt: false,
    requireDomain: false,
    showPaperIds: false,
    showBib: false,
    showDraft: true,
    showZotero: false,
  },
  {
    key: 'from_zotero',
    icon: '📕',
    label: 'From Zotero',
    desc: 'Import papers from your Zotero library',
    hint: 'Connect your Zotero library to use papers you\'ve already collected. Full-text PDFs from your institutional access produce much better results than abstract-only search.',
    promptLabel: 'Research focus (optional)',
    promptPlaceholder: 'e.g. Find what I\'m missing in this collection',
    requirePrompt: false,
    requireDomain: true,
    showPaperIds: false,
    showBib: false,
    showDraft: false,
    showZotero: true,
  },
] as const;

const PAPER_TYPES = [
  { key: 'proof', label: 'Proof Paper', desc: 'Theorems, lemmas, formal proofs' },
  { key: 'survey', label: 'Survey', desc: 'Taxonomy, comparison tables, trends' },
  { key: 'review', label: 'Systematic Review', desc: 'PRISMA methodology, screening, synthesis' },
  { key: 'experimental', label: 'Experimental', desc: 'Hypothesis testing, statistical analysis' },
  { key: 'discussion', label: 'Discussion', desc: 'Position paper, arguments, counterarguments' },
] as const;

const PAPER_TYPE_DEFAULTS: Record<string, string> = {
  detailed: 'proof',
  exploration: 'survey',
  reference: 'survey',
  from_bib: 'survey',
  from_draft: 'proof',
  from_zotero: 'survey',
};

export function NewSessionForm() {
  const allSessions = useSessionStore((s) => s.sessions);
  const lastSpec = allSessions.length > 0 ? allSessions[0]?.input_spec : undefined;

  const [mode, setModeState] = useState(() => {
    try { return localStorage.getItem('eurekalab_session_mode') || lastSpec?.mode || 'exploration'; } catch { return 'exploration'; }
  });
  const setMode = (m: string) => {
    setModeState(m);
    setPaperType(PAPER_TYPE_DEFAULTS[m] || 'survey');
    try { localStorage.setItem('eurekalab_session_mode', m); } catch { /* ignore */ }
  };
  const [domain, setDomain] = useState(() => lastSpec?.domain || '');
  const [prompt, setPrompt] = useState(() => lastSpec?.conjecture || lastSpec?.query || '');
  const [paperIds, setPaperIds] = useState(() => (lastSpec?.paper_ids ?? []).join('\n'));
  const [bibContent, setBibContent] = useState('');
  const [pdfDir, setPdfDir] = useState('');
  const [draftContent, setDraftContent] = useState('');
  const [zoteroCollectionId, setZoteroCollectionId] = useState('');
  const [paperType, setPaperType] = useState(() => PAPER_TYPE_DEFAULTS[mode] || 'survey');
  const [error, setError] = useState('');
  const [launching, setLaunching] = useState(false);

  const selectedSkills = useSkillStore((s) => s.selectedSkills);
  const sessions = allSessions;
  const setSessions = useSessionStore((s) => s.setSessions);
  const setCurrentRunId = useSessionStore((s) => s.setCurrentRunId);
  const setCurrentLogPage = useSessionStore((s) => s.setCurrentLogPage);
  const setActiveView = useUiStore((s) => s.setActiveView);

  const cfg = MODES.find((m) => m.key === mode) ?? MODES[1];

  const validate = (): string | null => {
    if (cfg.requireDomain && !domain.trim()) return `Research domain is required for this mode.`;
    if (cfg.requirePrompt && !prompt.trim()) return 'Please enter the research question or claim you want EurekaLab to investigate.';
    return null;
  };

  const buildPayload = () => {
    const skillCtx = selectedSkills.length ? `User-selected skills: ${selectedSkills.join(', ')}` : '';
    const ids = paperIds.split(/[\n,\s]+/).map((id: string) => id.trim()).filter(Boolean);
    const base = { domain: domain.trim(), query: prompt.trim(), additional_context: skillCtx, selected_skills: selectedSkills, paper_type: paperType };

    if (mode === 'reference') return { ...base, mode: 'reference', paper_ids: ids, query: prompt.trim() || `Find research gaps in ${domain}` };
    if (mode === 'exploration') return { ...base, mode: 'exploration', query: prompt.trim() || `Survey the frontier of ${domain} and identify open problems` };
    if (mode === 'from_bib') return { ...base, mode: 'from_bib', bib_content: bibContent, pdf_dir: pdfDir.trim() || undefined };
    if (mode === 'from_draft') return { ...base, mode: 'from_draft', draft_content: draftContent, draft_instruction: prompt.trim() };
    if (mode === 'from_zotero') return { ...base, mode: 'from_zotero', zotero_collection_id: zoteroCollectionId.trim() };
    return { ...base, mode: 'detailed', conjecture: prompt.trim() };
  };

  const handleLaunch = async () => {
    const validErr = validate();
    if (validErr) { setError(validErr); setTimeout(() => setError(''), 4000); return; }
    setError('');
    setLaunching(true);
    try {
      const run = await apiPost<SessionRun>('/api/runs', buildPayload());
      setSessions([run, ...sessions.filter((s) => s.run_id !== run.run_id)]);
      setCurrentRunId(run.run_id);
      setCurrentLogPage(1);
      setActiveView('workspace');
    } catch (err) {
      setError(`Could not start session: ${(err as Error).message}`);
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="new-session-pane" id="new-session-pane">
      <div className="new-session-card">
        <div className="canvas-heading">
          <h2 className="canvas-title">Start a Research Session</h2>
          <p className="canvas-sub">Choose how you want to begin, select your output type, and let EurekaLab do the heavy lifting.</p>
        </div>

        <div className="canvas-form-body">
          {/* Step 1: Choose entry mode */}
          <div className="canvas-step">
            <span className="canvas-step-label">1. How do you want to start?</span>
            <div className="canvas-mode-row">
              {MODES.map((m) => (
                <button
                  key={m.key}
                  className={`canvas-mode-card${mode === m.key ? ' is-active' : ''}`}
                  onClick={() => setMode(m.key)}
                  type="button"
                >
                  <span className="canvas-mode-icon">{m.icon}</span>
                  <span className="canvas-mode-label">{m.label}</span>
                  <span className="canvas-mode-desc">{m.desc}</span>
                </button>
              ))}
            </div>
            <p className="canvas-hint">{cfg.hint}</p>
          </div>

          {/* Step 2: Choose paper type */}
          <div className="canvas-step">
            <span className="canvas-step-label">2. What type of paper?</span>
            <div className="canvas-type-row">
              {PAPER_TYPES.map((pt) => (
                <button
                  key={pt.key}
                  className={`canvas-type-chip${paperType === pt.key ? ' is-active' : ''}`}
                  onClick={() => setPaperType(pt.key)}
                  type="button"
                  title={pt.desc}
                >
                  {pt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Step 3: Provide input */}
          <div className="canvas-step">
            <span className="canvas-step-label">3. Provide your input</span>

            {(cfg.requireDomain || mode !== 'detailed') && (
              <label className="canvas-full">
                <span className="canvas-label">Research domain</span>
                <input id="input-domain" type="text" value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="e.g. machine learning, neuroscience, quantum computing" />
              </label>
            )}

            {cfg.showPaperIds && (
              <label className="canvas-full">
                <span className="canvas-label">Paper IDs <em className="field-note">(arXiv or Semantic Scholar, one per line)</em></span>
                <textarea id="input-paper-ids" rows={2} value={paperIds} onChange={(e) => setPaperIds(e.target.value)} placeholder={'1706.03762\n2005.14165'} />
              </label>
            )}

            {cfg.showBib && (
              <>
                <label className="canvas-full">
                  <span className="canvas-label">BibTeX content <em className="field-note">(paste your .bib file)</em></span>
                  <textarea rows={5} value={bibContent} onChange={(e) => setBibContent(e.target.value)} placeholder={'@article{smith2024,\n  title = {Optimal Bounds},\n  author = {Smith, J.},\n  year = {2024},\n}'} />
                </label>
                <label className="canvas-full">
                  <span className="canvas-label">Local PDF directory <em className="field-note">(optional — for full-text extraction)</em></span>
                  <input type="text" value={pdfDir} onChange={(e) => setPdfDir(e.target.value)} placeholder="/path/to/papers/" />
                </label>
              </>
            )}

            {cfg.showDraft && (
              <label className="canvas-full">
                <span className="canvas-label">Draft paper <em className="field-note">(paste LaTeX, Markdown, or plain text)</em></span>
                <textarea rows={8} value={draftContent} onChange={(e) => setDraftContent(e.target.value)} placeholder={'Paste your work-in-progress here...'} />
              </label>
            )}

            {cfg.showZotero && (
              <label className="canvas-full">
                <span className="canvas-label">Zotero collection ID</span>
                <input type="text" value={zoteroCollectionId} onChange={(e) => setZoteroCollectionId(e.target.value)} placeholder="e.g. ABC123 (from your Zotero library URL)" />
                <em className="field-note">Configure ZOTERO_API_KEY and ZOTERO_LIBRARY_ID in Settings first</em>
              </label>
            )}

            <label className="canvas-full">
              <span className="canvas-label">{cfg.promptLabel}</span>
              <textarea id="input-prompt" rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={cfg.promptPlaceholder} />
            </label>
          </div>

          {/* Skills chips */}
          {selectedSkills.length > 0 && (
            <div className="canvas-skill-chips">
              {selectedSkills.map((name: string) => (
                <span key={name} className="intent-chip">{humanize(name)}</span>
              ))}
            </div>
          )}

          {/* Launch */}
          <div className="canvas-actions">
            <button className="canvas-launch-btn" id="launch-session-btn" disabled={launching} onClick={() => void handleLaunch()}>
              <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
              {launching ? 'Launching…' : 'Launch research session'}
            </button>
          </div>
          {error && <p className="canvas-error" id="canvas-error">{error}</p>}
        </div>
      </div>
    </div>
  );
}

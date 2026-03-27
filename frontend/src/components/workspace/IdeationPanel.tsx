import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/api/client';
import type { IdeationPoolState, InjectedIdea, ResearchDirection } from '@/types';

interface IdeationPanelProps {
  runId: string;
  ideationDone: boolean;
}

export function IdeationPanel({ runId, ideationDone }: IdeationPanelProps) {
  const [pool, setPool] = useState<IdeationPoolState | null>(null);
  const [ideaText, setIdeaText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchPool = useCallback(async () => {
    try {
      const data = await apiGet<IdeationPoolState>(`/api/runs/${runId}/ideation-pool`);
      setPool(data);
    } catch {
      setPool(null);
    }
  }, [runId]);

  useEffect(() => {
    if (!ideationDone) return;
    fetchPool();
    const interval = setInterval(fetchPool, 5000);
    return () => clearInterval(interval);
  }, [ideationDone, fetchPool]);

  const handleInject = async () => {
    if (!ideaText.trim()) return;
    setSubmitting(true);
    try {
      await apiPost(`/api/runs/${runId}/ideation-pool/inject`, {
        type: 'idea',
        text: ideaText.trim(),
        source: 'ui',
      });
      setIdeaText('');
      await fetchPool();
    } catch (err) {
      console.error('Inject failed:', err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!pool || (!pool.directions.length && !pool.injected_ideas.length)) return null;

  return (
    <div className="ideation-panel">
      <div className="ideation-header">
        <span className="ideation-title">Ideation Pool</span>
        <span className="ideation-version">v{pool.version}</span>
      </div>

      {pool.selected_direction && (
        <div className="ideation-selected">
          <span className="ideation-star">★</span>
          <div>
            <span className="ideation-dir-title">{pool.selected_direction.title}</span>
            {pool.selected_direction.composite_score != null && (
              <span className="ideation-score">({pool.selected_direction.composite_score.toFixed(2)})</span>
            )}
          </div>
        </div>
      )}

      {pool.directions.filter((d: ResearchDirection) => d.title !== pool.selected_direction?.title).length > 0 && (
        <div className="ideation-other-dirs">
          {pool.directions
            .filter((d: ResearchDirection) => d.title !== pool.selected_direction?.title)
            .slice(0, 4)
            .map((d: ResearchDirection, i: number) => (
              <div key={i} className="ideation-dir-item">
                <span className="ideation-dir-bullet">○</span>
                <span>{d.title}</span>
                {d.composite_score != null && (
                  <span className="ideation-score">({d.composite_score.toFixed(2)})</span>
                )}
              </div>
            ))}
        </div>
      )}

      {pool.injected_ideas.length > 0 && (
        <div className="ideation-ideas">
          <span className="ideation-section-label">Injected Ideas ({pool.injected_ideas.length})</span>
          {pool.injected_ideas.map((idea: InjectedIdea, i: number) => (
            <div key={i} className={`ideation-idea${idea.incorporated ? ' is-incorporated' : ''}`}>
              <span className="ideation-idea-icon">{idea.incorporated ? '✓' : '💡'}</span>
              <span className="ideation-idea-text">{idea.text.slice(0, 120)}</span>
              <span className="ideation-idea-source">{idea.source}</span>
            </div>
          ))}
        </div>
      )}

      {pool.emerged_insights.length > 0 && (
        <div className="ideation-insights">
          <span className="ideation-section-label">Theory Insights ({pool.emerged_insights.length})</span>
          {pool.emerged_insights.slice(0, 3).map((insight: string, i: number) => (
            <div key={i} className="ideation-insight">
              <span className="ideation-insight-icon">🔍</span>
              <span>{insight.slice(0, 150)}</span>
            </div>
          ))}
        </div>
      )}

      <div className="ideation-inject-row">
        <input
          type="text"
          className="ideation-inject-input"
          placeholder="Inject an idea…"
          value={ideaText}
          onChange={(e) => setIdeaText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !submitting) void handleInject(); }}
          disabled={submitting}
        />
        <button
          className="btn btn-primary btn-sm"
          disabled={submitting || !ideaText.trim()}
          onClick={() => void handleInject()}
        >
          Inject
        </button>
      </div>
    </div>
  );
}

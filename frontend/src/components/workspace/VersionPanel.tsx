import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPost } from '@/api/client';
import type { SessionRun, VersionEntry } from '@/types';

interface VersionPanelProps {
  run: SessionRun | null;
  isVisible?: boolean;
}

function formatAge(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function triggerColor(trigger: string): string {
  if (trigger.includes('FAILED')) return 'var(--red, #e55)';
  if (trigger.startsWith('checkout')) return 'var(--blue, #58f)';
  if (trigger.startsWith('inject')) return 'var(--amber, #fa3)';
  return 'var(--green, #5a5)';
}

function triggerIcon(trigger: string): string {
  if (trigger.includes('FAILED')) return '✗';
  if (trigger.startsWith('checkout')) return '↩';
  if (trigger.startsWith('inject')) return '⊕';
  return '●';
}

export function VersionPanel({ run, isVisible = true }: VersionPanelProps) {
  const [versions, setVersions] = useState<VersionEntry[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [diffResult, setDiffResult] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [checkoutMsg, setCheckoutMsg] = useState('');

  const runId = run?.run_id;

  const fetchVersions = useCallback(async () => {
    if (!runId) return;
    try {
      const data = await apiGet<{ versions: VersionEntry[] }>(`/api/runs/${runId}/versions`);
      setVersions(data.versions ?? []);
    } catch {
      setVersions([]);
    }
  }, [runId]);

  useEffect(() => {
    if (!isVisible) return;
    fetchVersions();
    const interval = setInterval(fetchVersions, 5000);
    return () => clearInterval(interval);
  }, [fetchVersions, isVisible]);

  const handleDiff = async () => {
    if (selected.length !== 2 || !runId) return;
    setLoading(true);
    try {
      const [v1, v2] = selected.sort((a, b) => a - b);
      const data = await apiPost<{ changes: string[] }>(`/api/runs/${runId}/versions/diff`, { v1, v2 });
      setDiffResult(data.changes ?? []);
    } catch (err) {
      setDiffResult([`Error: ${(err as Error).message}`]);
    } finally {
      setLoading(false);
    }
  };

  const handleCheckout = async (versionNumber: number) => {
    if (!runId) return;
    if (!confirm(`Restore to v${String(versionNumber).padStart(3, '0')}? Current HEAD will be preserved.`)) return;
    setLoading(true);
    try {
      const data = await apiPost<{ ok: boolean; new_head: number; completed_stages: string[] }>(
        `/api/runs/${runId}/versions/checkout`,
        { version_number: versionNumber },
      );
      setCheckoutMsg(`Restored to v${String(versionNumber).padStart(3, '0')}. New HEAD: v${String(data.new_head).padStart(3, '0')}`);
      await fetchVersions();
      setSelected([]);
      setDiffResult([]);
    } catch (err) {
      setCheckoutMsg(`Checkout failed: ${(err as Error).message}`);
    } finally {
      setLoading(false);
      setTimeout(() => setCheckoutMsg(''), 5000);
    }
  };

  const toggleSelect = (vn: number) => {
    setSelected((prev) => {
      if (prev.includes(vn)) return prev.filter((n) => n !== vn);
      if (prev.length >= 2) return [prev[1], vn];
      return [...prev, vn];
    });
    setDiffResult([]);
  };

  if (!run) {
    return (
      <div className="version-panel">
        <p className="drawer-muted">Select a session to view version history.</p>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="version-panel">
        <p className="drawer-muted">No versions recorded yet. Versions are created after each pipeline stage completes.</p>
      </div>
    );
  }

  return (
    <div className="version-panel">
      <div className="version-header">
        <h3 className="version-title">Version History</h3>
        <div className="version-actions">
          {selected.length === 2 && (
            <button className="btn btn-secondary btn-sm" onClick={() => void handleDiff()} disabled={loading}>
              Compare v{Math.min(...selected)} → v{Math.max(...selected)}
            </button>
          )}
        </div>
      </div>

      {checkoutMsg && (
        <div className="version-checkout-msg">{checkoutMsg}</div>
      )}

      <div className="version-timeline">
        {[...versions].reverse().map((v) => {
          const isHead = v.version_number === versions[versions.length - 1]?.version_number;
          const isSelected = selected.includes(v.version_number);
          return (
            <div
              key={v.version_number}
              className={`version-entry${isSelected ? ' is-selected' : ''}${isHead ? ' is-head' : ''}`}
              onClick={() => toggleSelect(v.version_number)}
            >
              <span className="version-dot" style={{ color: triggerColor(v.trigger) }}>
                {triggerIcon(v.trigger)}
              </span>
              <div className="version-info">
                <span className="version-label">
                  v{String(v.version_number).padStart(3, '0')}
                  {isHead && <span className="version-head-badge">HEAD</span>}
                </span>
                <span className="version-trigger">{v.trigger}</span>
                {v.changes.length > 0 && (
                  <span className="version-changes">{v.changes[0]}</span>
                )}
              </div>
              <div className="version-meta">
                <span className="version-age">{formatAge(v.timestamp)}</span>
                <button
                  className="version-checkout-btn"
                  title={`Restore to v${String(v.version_number).padStart(3, '0')}`}
                  onClick={(e) => { e.stopPropagation(); void handleCheckout(v.version_number); }}
                  disabled={loading || isHead}
                >
                  ↩
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {diffResult.length > 0 && (
        <div className="version-diff">
          <h4 className="version-diff-title">
            Changes v{Math.min(...selected)} → v{Math.max(...selected)}
          </h4>
          {diffResult.map((change, i) => (
            <div
              key={i}
              className={`version-diff-line${
                change.includes('+paper') || change.includes('+proven') || change.includes('+direction')
                  ? ' diff-add'
                  : change.includes('removed') || change.startsWith('Removed')
                  ? ' diff-remove'
                  : ' diff-change'
              }`}
            >
              {change}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useState, useEffect } from 'react';
import { apiGet } from '@/api/client';
import type { ContentGapReport } from '@/types';

interface ContentGapBannerProps {
  runId: string;
  surveyDone: boolean;
}

export function ContentGapBanner({ runId, surveyDone }: ContentGapBannerProps) {
  const [report, setReport] = useState<ContentGapReport | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!surveyDone || dismissed) return;
    apiGet<ContentGapReport>(`/api/runs/${runId}/content-gap`)
      .then(setReport)
      .catch(() => setReport(null));
  }, [runId, surveyDone, dismissed]);

  if (!report || !report.has_gaps || dismissed) return null;

  return (
    <div className="content-gap-banner">
      <div className="content-gap-header">
        <span className="content-gap-icon">⚠</span>
        <span className="content-gap-title">Content Gaps Detected</span>
        <button className="content-gap-dismiss" onClick={() => setDismissed(true)} title="Dismiss">×</button>
      </div>
      <div className="content-gap-stats">
        <span className="gap-stat gap-full">Full text: {report.full_text}</span>
        <span className="gap-stat gap-abstract">Abstract only: {report.abstract_only}</span>
        <span className="gap-stat gap-metadata">Metadata only: {report.metadata_only}</span>
        {report.missing > 0 && <span className="gap-stat gap-missing">Missing: {report.missing}</span>}
      </div>
      {report.degraded_papers.length > 0 && (
        <div className="content-gap-papers">
          {report.degraded_papers.slice(0, 5).map((p: ContentGapReport['degraded_papers'][number]) => (
            <div key={p.paper_id} className="gap-paper">
              <span className={`gap-tier gap-tier--${p.content_tier}`}>{p.content_tier}</span>
              <span className="gap-paper-title">{p.title?.slice(0, 60)}</span>
              {p.arxiv_id && <span className="gap-paper-id">{p.arxiv_id}</span>}
            </div>
          ))}
        </div>
      )}
      <p className="content-gap-hint">
        Papers with limited content produce weaker results. Use <code>eurekaclaw inject paper</code> to add full PDFs.
      </p>
    </div>
  );
}

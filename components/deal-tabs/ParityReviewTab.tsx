'use client';

import ParityReviewChat from '@/components/ParityReviewChat';
import type { Deal, Entity } from '@/lib/v1-api';
import type { AnalysisState, QueuedStatement } from './types';

export interface ParityReviewTabProps {
  deal: Deal | null;
  entities: Entity[];
  rawTransactions: Array<Record<string, unknown>>;
  creditScoringInputs: Record<string, unknown> | null;
  confidence: number | null;
  analysisState: AnalysisState;
  statementQueue: QueuedStatement[];
  needsReviewItems: Array<Record<string, unknown>>;
  onGoToQueue: () => void;
  onGoToSnapshot: () => void;
}

export default function ParityReviewTab({
  deal,
  entities,
  rawTransactions,
  creditScoringInputs,
  confidence,
  analysisState,
  statementQueue,
  needsReviewItems,
  onGoToQueue,
  onGoToSnapshot,
}: ParityReviewTabProps) {
  if (!deal) return null;
  const classified = entities.length;
  const txnTotal = rawTransactions.length;
  const reconDelta = creditScoringInputs ? (creditScoringInputs.average_net_monthly_cents as number ?? 0) : 0;
  const corpusReady = analysisState === 'done';
  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
      {/* Left: Chat area — isolated component to avoid full-page re-renders on keystroke */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <ParityReviewChat
          dealId={deal.id}
          corpusReady={corpusReady}
          txnTotal={txnTotal}
          statementCount={statementQueue.filter(s => s.status === 'ready').length}
        />
      </div>

      {/* Right: Corpus state sidebar */}
      <div style={{ width: 220, flexShrink: 0 }}>
        <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 16, marginBottom: 12 }}>
          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: '#374151', marginBottom: 14 }}>CORPUS STATE</div>
          {[
            { label: 'Transactions', value: txnTotal > 0 ? String(txnTotal) : '—' },
            { label: 'Classified', value: classified > 0 ? `${classified} entities` : '—' },
            { label: 'Entities', value: entities.length > 0 ? String(entities.length) : '—' },
            { label: 'Needs review', value: needsReviewItems.length > 0 ? String(needsReviewItems.length) : '0' },
            { label: 'Recon delta', value: reconDelta !== 0 ? `${(reconDelta / 100).toLocaleString('en-KE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—' },
            { label: 'Confidence', value: confidence != null ? `${(Number(confidence) * 100).toFixed(1)}%` : '—' },
          ].map(({ label, value }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
              <span style={{ fontSize: 11, color: '#4A5568' }}>{label}</span>
              <span style={{ fontSize: 12, color: '#94A3B8', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>{value}</span>
            </div>
          ))}
        </div>

        {/* Override queue */}
        <button
          onClick={onGoToQueue}
          style={{ width: '100%', padding: '9px 12px', background: 'transparent', border: '1px solid #1E2A3A', borderRadius: 6, color: '#64748B', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif", textAlign: 'left', marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#14B8A6'; (e.currentTarget as HTMLElement).style.color = '#5EEAD4'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#1E2A3A'; (e.currentTarget as HTMLElement).style.color = '#64748B'; }}
        >
          <span>Review queue</span>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: needsReviewItems.length > 0 ? '#F59E0B' : '#374151' }}>({needsReviewItems.length}) →</span>
        </button>

        <button
          onClick={onGoToSnapshot}
          style={{ width: '100%', padding: '9px 12px', background: 'rgba(20,184,166,0.1)', border: '1px solid rgba(20,184,166,0.25)', borderRadius: 6, color: '#5EEAD4', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(20,184,166,0.18)'; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'rgba(20,184,166,0.1)'; }}
        >
          Export snapshot
        </button>
      </div>
    </div>
  );
}

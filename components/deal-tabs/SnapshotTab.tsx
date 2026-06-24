'use client';

import type { AnalysisRun, Snapshot } from '@/lib/v1-api';
import type { AnalysisState } from './types';

export interface SnapshotTabProps {
  run: AnalysisRun | undefined;
  snapshot: Snapshot | undefined;
  analysisState: AnalysisState;
  onReExport: () => Promise<void>;
  onDownloadCSV: () => Promise<void>;
  exportSuccess: string;
  exportError: string;
  lastExportedAt: Date | null;
}

export default function SnapshotTab({
  run,
  snapshot,
  analysisState,
  onReExport,
  onDownloadCSV,
  exportSuccess,
  exportError,
  lastExportedAt,
}: SnapshotTabProps) {
  return (
    <div style={{ maxWidth: 720 }}>
      {!run ? (
        <div style={{ padding: '48px 0', textAlign: 'center', color: '#374151', fontSize: 13 }}>
          Run analysis first to generate a snapshot.
        </div>
      ) : (
        <>
          <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20, marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1', marginBottom: 14 }}>EXPORT SNAPSHOT</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
              <button onClick={onReExport} disabled={analysisState === 'exporting'}
                style={{ padding: '9px 18px', background: '#6366F1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: analysisState === 'exporting' ? 'not-allowed' : 'pointer', opacity: analysisState === 'exporting' ? 0.6 : 1 }}>
                {analysisState === 'exporting' ? 'Generating PDF…' : 'Save & Export PDF'}
              </button>
              <button onClick={onDownloadCSV}
                style={{ padding: '9px 18px', background: 'transparent', color: '#94A3B8', border: '1px solid #1E2A3A', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>
                Download CSV
              </button>
            </div>
            {exportSuccess && <div style={{ fontSize: 12, color: '#4ADE80', marginBottom: 10 }}>{exportSuccess}</div>}
            {exportError && <div style={{ fontSize: 12, color: '#F87171', marginBottom: 10 }}>{exportError}</div>}
            {lastExportedAt && <div style={{ fontSize: 11, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>Last exported {lastExportedAt.toLocaleTimeString()}</div>}
          </div>

          {snapshot && (
            <div style={{ background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 8, padding: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: '#CBD5E1', marginBottom: 14 }}>SNAPSHOT HASHES</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  { label: 'snapshot_id', value: snapshot.id },
                  { label: 'sha256_hash', value: snapshot.sha256_hash },
                  { label: 'financial_state_hash', value: snapshot.financial_state_hash },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div style={{ fontSize: 10, color: '#374151', marginBottom: 3, letterSpacing: '0.08em' }}>{label}</div>
                    <div style={{ fontSize: 12, color: '#4A5568', fontFamily: "'IBM Plex Mono', monospace", wordBreak: 'break-all' }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

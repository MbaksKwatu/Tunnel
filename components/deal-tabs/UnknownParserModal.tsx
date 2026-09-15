'use client';

import type { ParserRequestDoc, ParserRequestForm } from './types';

const MAX_RETRY_ATTEMPTS = 3;

export interface UnknownParserModalProps {
  doc: ParserRequestDoc | null;
  form: ParserRequestForm;
  setForm: React.Dispatch<React.SetStateAction<ParserRequestForm>>;
  submitting: boolean;
  submitted: boolean;
  retrying: boolean;
  onSubmit: () => Promise<void>;
  onClose: () => void;
  onRetry?: () => Promise<void>;
}

export default function UnknownParserModal({
  doc,
  form,
  setForm,
  submitting,
  submitted,
  retrying,
  onSubmit,
  onClose,
  onRetry,
}: UnknownParserModalProps) {
  if (!doc) return null;

  const isInvalidDocument = doc.failureCategory === 'invalid_document';
  const retryCount = doc.retryCount ?? 0;
  const attemptsRemaining = MAX_RETRY_ATTEMPTS - retryCount;
  const retriesExhausted = retryCount >= MAX_RETRY_ATTEMPTS;

  // Category A: corrupt/wrong file — no modal, just a clear error with no actions
  if (isInvalidDocument) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(8,12,24,0.85)', backdropFilter: 'blur(4px)' }}>
        <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, width: 480, maxWidth: '90vw', padding: 28, boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red)', display: 'inline-block' }} />
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--red)', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>UNREADABLE FILE</span>
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--t0)', margin: 0 }}>This file could not be read</h3>
              <p style={{ fontSize: 12, color: 'var(--t2)', marginTop: 6, lineHeight: 1.5 }}>
                <span style={{ color: 'var(--t2)', fontFamily: "'IBM Plex Mono', monospace" }}>{doc.fileName}</span> could not be parsed as a bank statement.
                It may be corrupt, an unsupported file format, or not a bank statement PDF at all.
              </p>
              <p style={{ fontSize: 12, color: 'var(--t2)', marginTop: 8, lineHeight: 1.5 }}>
                Please check the file and upload a different one. There is nothing to retry here — the file itself needs to change.
              </p>
            </div>
            <button
              onClick={onClose}
              style={{ background: 'transparent', border: 'none', color: 'var(--t2)', fontSize: 18, cursor: 'pointer', padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0 }}
            >×</button>
          </div>
          <button
            onClick={onClose}
            style={{ width: '100%', padding: '10px 0', background: 'var(--s3)', color: 'var(--t1)', border: '1px solid var(--b1)', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  // Category B: valid document but unsupported bank — parser-request modal + retry
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(8,12,24,0.85)', backdropFilter: 'blur(4px)' }}>
      <div style={{ background: 'var(--s1)', border: '1px solid var(--b1)', borderRadius: 10, width: 480, maxWidth: '90vw', padding: 28, boxShadow: '0 24px 64px rgba(0,0,0,0.6)' }}>
        {!submitted ? (
          <>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 20 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--amber)', display: 'inline-block' }} />
                  <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--amber)', letterSpacing: '0.1em', fontFamily: "'IBM Plex Mono', monospace" }}>UNSUPPORTED BANK FORMAT</span>
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--t0)', margin: 0 }}>Parser not found for this bank</h3>
                <p style={{ fontSize: 12, color: 'var(--t2)', marginTop: 6, lineHeight: 1.5 }}>
                  <span style={{ color: 'var(--t2)', fontFamily: "'IBM Plex Mono', monospace" }}>{doc.fileName}</span> is a valid bank statement but uses a format we don't currently support.
                  Request a parser and we'll add it to the pipeline.
                </p>
              </div>
              <button
                onClick={onClose}
                style={{ background: 'transparent', border: 'none', color: 'var(--t2)', fontSize: 18, cursor: 'pointer', padding: '0 0 0 12px', lineHeight: 1, flexShrink: 0 }}
              >×</button>
            </div>

            {/* Retry section (if retries remain and not exhausted) */}
            {!retriesExhausted && onRetry && (
              <div style={{ marginBottom: 16, padding: '10px 14px', background: 'rgba(129,140,248,0.07)', border: '1px solid rgba(129,140,248,0.2)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: 'var(--t1)', marginBottom: 8 }}>
                  If a parser for this bank was recently added, try re-running it now.
                  <span style={{ marginLeft: 6, color: 'var(--t2)', fontFamily: "'IBM Plex Mono', monospace" }}>
                    {attemptsRemaining} of {MAX_RETRY_ATTEMPTS} attempt{attemptsRemaining !== 1 ? 's' : ''} remaining
                  </span>
                </div>
                <button
                  onClick={onRetry}
                  disabled={retrying}
                  style={{ padding: '6px 14px', background: retrying ? 'var(--s3)' : 'rgba(129,140,248,0.15)', color: retrying ? 'var(--t2)' : '#818CF8', border: '1px solid rgba(129,140,248,0.3)', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: retrying ? 'not-allowed' : 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
                >
                  {retrying ? 'Retrying…' : '↺ Retry parser'}
                </button>
              </div>
            )}

            {/* Exhausted retries state */}
            {retriesExhausted && (
              <div style={{ marginBottom: 16, padding: '10px 14px', background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.25)', borderRadius: 6 }}>
                <div style={{ fontSize: 11, color: '#FCA5A5', fontWeight: 600, marginBottom: 4 }}>Retry attempts exhausted</div>
                <div style={{ fontSize: 11, color: 'var(--t1)', lineHeight: 1.5 }}>
                  All {MAX_RETRY_ATTEMPTS} attempts used. You can request a parser below, delete the file from this deal, or leave it in the queue for when the parser is ready.
                </div>
              </div>
            )}

            {/* Request parser form */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--t2)', marginBottom: 5, letterSpacing: '0.06em' }}>BANK NAME *</label>
                <input
                  type="text"
                  value={form.bankName}
                  onChange={(e) => setForm((p) => ({ ...p, bankName: e.target.value }))}
                  placeholder="e.g. Stanbic Bank, Absa, DTB"
                  autoFocus
                  style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--b1)', borderRadius: 6, padding: '8px 12px', color: 'var(--t0)', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: "'IBM Plex Sans', sans-serif" }}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--t2)', marginBottom: 5, letterSpacing: '0.06em' }}>COUNTRY</label>
                  <select
                    value={form.country}
                    onChange={(e) => setForm((p) => ({ ...p, country: e.target.value }))}
                    style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--b1)', borderRadius: 6, padding: '8px 12px', color: 'var(--t1)', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                  >
                    {['Kenya', 'Nigeria', 'Uganda', 'Tanzania', 'Ghana', 'South Africa', 'Rwanda', 'Ethiopia', 'Other'].map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--t2)', marginBottom: 5, letterSpacing: '0.06em' }}>ACCOUNT TYPE</label>
                  <select
                    value={form.accountType}
                    onChange={(e) => setForm((p) => ({ ...p, accountType: e.target.value }))}
                    style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--b1)', borderRadius: 6, padding: '8px 12px', color: 'var(--t1)', fontSize: 13, outline: 'none', boxSizing: 'border-box' }}
                  >
                    {['Business Current', 'Business Savings', 'Personal Current', 'Personal Savings', 'Mobile Money', 'Other'].map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--t2)', marginBottom: 5, letterSpacing: '0.06em' }}>NOTES <span style={{ color: 'var(--b1)' }}>optional</span></label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
                  placeholder="Any additional info about the format — e.g. PDF vs CSV, layout description…"
                  rows={2}
                  style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--b1)', borderRadius: 6, padding: '8px 12px', color: 'var(--t1)', fontSize: 12, outline: 'none', resize: 'none', boxSizing: 'border-box', fontFamily: "'IBM Plex Sans', sans-serif" }}
                />
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
              <button
                onClick={onSubmit}
                disabled={!form.bankName.trim() || submitting}
                style={{ flex: 1, padding: '10px 0', background: !form.bankName.trim() || submitting ? 'var(--s3)' : 'var(--accent)', color: !form.bankName.trim() || submitting ? 'var(--t2)' : '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: !form.bankName.trim() || submitting ? 'not-allowed' : 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
              >
                {submitting ? 'Submitting…' : 'Request parser →'}
              </button>
              <button
                onClick={onClose}
                style={{ padding: '10px 16px', background: 'transparent', color: 'var(--t2)', border: '1px solid var(--b1)', borderRadius: 6, fontSize: 13, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
              >
                Cancel
              </button>
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: 'var(--t2)', textAlign: 'center' }}>
              Cancelling keeps the file in the deal. It can be retried or deleted later.
            </div>
          </>
        ) : (
          /* Confirmation */
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(20,184,166,0.12)', border: '1px solid rgba(20,184,166,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 10l4.5 4.5L16 6" stroke="#5EEAD4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--t0)', margin: '0 0 8px' }}>Parser request submitted</h3>
            <p style={{ fontSize: 13, color: 'var(--t2)', margin: '0 0 20px', lineHeight: 1.5 }}>
              We've logged <strong style={{ color: 'var(--accent)' }}>{form.bankName}</strong> ({form.country}) for the engineering queue. You'll be able to re-run or re-upload once the parser is live.
            </p>
            <button
              onClick={onClose}
              style={{ padding: '9px 20px', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

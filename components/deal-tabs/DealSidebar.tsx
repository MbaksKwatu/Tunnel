'use client';

import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabase';
import type { Deal, DealListItem } from '@/lib/v1-api';

export type DealTab = 'documents' | 'analysis' | 'review' | 'queue' | 'snapshot';

export interface DealSidebarProps {
  deal: Deal | null;
  dealName: string;
  dealId: string | null;
  sidebarDeals: DealListItem[];
  pinnedDealIds: Set<string>;
  togglePinDeal: (dealId: string) => void;
  showDealList: boolean;
  setShowDealList: (show: boolean) => void;
  activeTab: DealTab;
  setActiveTab: (tab: DealTab) => void;
  needsReviewCount: number;
}

export default function DealSidebar({
  deal,
  dealName,
  dealId,
  sidebarDeals,
  pinnedDealIds,
  togglePinDeal,
  showDealList,
  setShowDealList,
  activeTab,
  setActiveTab,
  needsReviewCount,
}: DealSidebarProps) {
  const router = useRouter();

  return (
    <aside style={{ width: 200, background: '#0A0F1E', borderRight: '1px solid #1A2235', display: 'flex', flexDirection: 'column', padding: '20px 0', position: 'fixed', top: 0, left: 0, bottom: 0, zIndex: 50, flexShrink: 0 }}>
      <div style={{ padding: '0 16px 20px', borderBottom: '1px solid #1A2235' }}>
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, color: '#6366F1', letterSpacing: '0.08em', fontWeight: 700 }}>P/ PARITY<span style={{ fontSize: 9, verticalAlign: 'super', color: '#4A5568' }}>v2.0</span></div>
        {dealName && <div style={{ fontSize: 10, color: '#4A5568', marginTop: 6, letterSpacing: '0.08em', background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 4, padding: '3px 8px', display: 'inline-flex', gap: 6 }}>{dealName.toUpperCase()}</div>}
      </div>
      <nav style={{ flex: 1, padding: '12px 0', overflowY: 'auto' }}>
        {/* Pinned deals + Deals browser */}
        <button
          onClick={() => setShowDealList(!showDealList)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '6px 16px 8px', background: 'transparent', border: 'none', cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}
        >
          <span style={{ fontSize: 9, fontWeight: 700, color: '#2D3748', letterSpacing: '0.1em' }}>PINNED</span>
          <span style={{ fontSize: 9, color: '#374151', fontFamily: "'IBM Plex Mono', monospace" }}>{pinnedDealIds.size > 0 ? pinnedDealIds.size : ''}</span>
        </button>
        {/* Pinned deals — always visible */}
        {sidebarDeals.filter(d => pinnedDealIds.has(d.id)).map((d) => {
          const isActive = deal?.id === d.id;
          const name = (d.company_name || d.name || 'Untitled') as string;
          return (
            <div key={d.id} style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
              <button
                onClick={() => router.push(`/v1/deal?deal_id=${d.id}`)}
                style={{ flex: 1, display: 'block', padding: '6px 4px 6px 18px', background: isActive ? 'rgba(99,102,241,0.08)' : 'transparent', borderLeft: isActive ? '2px solid #6366F1' : '2px solid transparent', border: 'none', color: isActive ? '#A5B4FC' : '#64748B', fontSize: 11, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
              >
                {name}
              </button>
              <button
                onClick={() => togglePinDeal(d.id)}
                title="Unpin deal"
                style={{ padding: '2px 8px', background: 'transparent', border: 'none', color: '#2D3748', fontSize: 10, cursor: 'pointer', fontFamily: "'IBM Plex Mono', monospace", flexShrink: 0 }}
              >x</button>
            </div>
          );
        })}

        {/* All deals overlay */}
        {showDealList && (
          <div style={{ margin: '4px 8px', background: '#0D1220', border: '1px solid #1E2A3A', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ padding: '8px 10px', borderBottom: '1px solid #1A2235', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: '#374151', letterSpacing: '0.1em' }}>ALL DEALS</span>
              <button onClick={() => setShowDealList(false)} style={{ background: 'transparent', border: 'none', color: '#374151', fontSize: 12, cursor: 'pointer', padding: 0, lineHeight: 1 }}>x</button>
            </div>
            {sidebarDeals.length === 0 && (
              <div style={{ padding: '10px', fontSize: 11, color: '#2D3748' }}>No deals yet</div>
            )}
            {sidebarDeals.map((d) => {
              const isPinned = pinnedDealIds.has(d.id);
              const name = (d.company_name || d.name || 'Untitled') as string;
              return (
                <div key={d.id} style={{ display: 'flex', alignItems: 'center', padding: '5px 10px', borderBottom: '1px solid #1A2235', gap: 6 }}>
                  <button
                    onClick={() => { router.push(`/v1/deal?deal_id=${d.id}`); setShowDealList(false); }}
                    style={{ flex: 1, background: 'transparent', border: 'none', color: '#64748B', fontSize: 11, cursor: 'pointer', textAlign: 'left', fontFamily: "'IBM Plex Sans', sans-serif", padding: '2px 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  >{name}</button>
                  <button
                    onClick={() => togglePinDeal(d.id)}
                    style={{ padding: '2px 6px', background: isPinned ? 'rgba(99,102,241,0.1)' : 'transparent', border: `1px solid ${isPinned ? '#6366F1' : '#1E2A3A'}`, borderRadius: 3, fontSize: 9, color: isPinned ? '#A5B4FC' : '#374151', cursor: 'pointer', fontFamily: "'IBM Plex Mono', monospace", flexShrink: 0 }}
                  >{isPinned ? 'UNPIN' : 'PIN'}</button>
                </div>
              );
            })}
            <button
              onClick={() => { router.push('/deals/new'); setShowDealList(false); }}
              style={{ display: 'block', width: '100%', padding: '8px 10px', background: 'transparent', border: 'none', color: '#6366F1', fontSize: 11, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left' }}
            >+ New deal</button>
          </div>
        )}

        {/* Divider */}
        {deal && <div style={{ margin: '4px 16px 8px', borderTop: '1px solid #1A2235' }} />}

        {[
          { label: 'Documents', tab: 'documents' as const },
          { label: 'Analysis', tab: 'analysis' as const },
          { label: 'Parity Review', tab: 'review' as const },
          { label: 'Review Queue', tab: 'queue' as const, badge: needsReviewCount > 0 ? needsReviewCount : undefined },
          { label: 'Snapshot', tab: 'snapshot' as const },
        ].map((item) => (
          <button
            key={item.tab}
            onClick={() => setActiveTab(item.tab)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 16px', background: activeTab === item.tab ? 'rgba(99,102,241,0.1)' : 'transparent', borderLeft: activeTab === item.tab ? '2px solid #6366F1' : '2px solid transparent', border: 'none', color: activeTab === item.tab ? '#A5B4FC' : '#4A5568', fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left' }}
          >
            <span>{item.label}</span>
            {'badge' in item && item.badge != null && (
              <span style={{ fontSize: 9, fontWeight: 700, color: '#F59E0B', background: 'rgba(245,158,11,0.1)', padding: '1px 5px', borderRadius: 3, fontFamily: "'IBM Plex Mono', monospace" }}>{item.badge}</span>
            )}
          </button>
        ))}
        <div style={{ margin: '12px 0 4px', padding: '0 16px', fontSize: 9, color: '#2D3748', letterSpacing: '0.1em' }}>DEAL TOOLS</div>
        {['Benchmark', 'Monitor', 'Registry'].map((label) => (
          <div key={label} style={{ padding: '9px 16px', color: '#2D3748', fontSize: 13, borderLeft: '2px solid transparent', display: 'flex', alignItems: 'center', gap: 8 }}>
            {label}
            <span style={{ fontSize: 9, background: '#0D1220', color: '#2D3748', padding: '1px 4px', borderRadius: 2 }}>SOON</span>
          </div>
        ))}
        <div style={{ margin: '12px 0 4px', padding: '0 16px', fontSize: 9, color: '#2D3748', letterSpacing: '0.1em' }}>FORMAT DESK</div>
        <button
          onClick={() => router.push('/parsers/request')}
          style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '9px 16px', background: 'transparent', borderLeft: '2px solid transparent', border: 'none', color: '#4A5568', fontSize: 13, fontFamily: "'IBM Plex Sans', sans-serif", cursor: 'pointer', textAlign: 'left', gap: 6 }}
        >
          <span style={{ fontSize: 11, lineHeight: 1, fontFamily: "'IBM Plex Mono', monospace", color: '#374151' }}>//</span>
          New Bank Format
        </button>
      </nav>
      <div style={{ padding: '12px 16px', borderTop: '1px solid #1A2235' }}>
        {dealId && (
          <div style={{ fontSize: 10, color: '#2D3748', fontFamily: "'IBM Plex Mono', monospace", marginBottom: 10, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {dealId.slice(0, 8)}…
          </div>
        )}
        <button onClick={() => { if (supabase) supabase.auth.signOut(); router.push('/login'); }} style={{ width: '100%', padding: '6px 0', background: 'transparent', border: '1px solid #1A2235', borderRadius: 4, color: '#374151', fontSize: 12, cursor: 'pointer', fontFamily: "'IBM Plex Sans', sans-serif" }}>
          Sign out
        </button>
      </div>
    </aside>
  );
}

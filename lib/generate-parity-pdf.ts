import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type { Deal, AnalysisRun, Snapshot, Entity } from './v1-api';

export interface PdfEntityRow {
  entityId: string;
  entityName: string;
  role: string;
  totalAbsCents: number;
  pctOfTotal: number;
  txnCount: number;
}

export interface GeneratePdfInput {
  deal: Deal;
  run: AnalysisRun;
  snapshot: Snapshot;
  entities: Entity[];
  entityBreakdown: PdfEntityRow[];
  overridesList: Array<Record<string, unknown>>;
  txCount: number;
  currency: string;
  topSuppliers: PdfEntityRow[];
  topRevenue: PdfEntityRow[];
  totalOutflow: number;
  payrollTotal: number;
  largestRevenuePct: number;
}

function fmtCents(cents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

function fmtBp(bp: number): string {
  return (bp / 100).toFixed(2) + '%';
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function checkPageBreak(doc: jsPDF, y: number, needed: number, margin: number): number {
  const pageH = doc.internal.pageSize.getHeight();
  if (y + needed > pageH - margin) {
    doc.addPage();
    return margin;
  }
  return y;
}

function sectionHeader(doc: jsPDF, text: string, x: number, y: number): number {
  doc.setFontSize(9);
  doc.setFont('courier', 'bold');
  doc.text(text, x, y);
  return y + 14;
}

function bodyLine(doc: jsPDF, text: string, x: number, y: number): number {
  doc.setFontSize(8);
  doc.setFont('courier', 'normal');
  doc.text(text, x, y);
  return y + 12;
}

export function generateParityPdf(input: GeneratePdfInput): void {
  const {
    deal,
    run,
    snapshot,
    entities,
    entityBreakdown,
    overridesList,
    txCount,
    currency,
    topSuppliers,
    topRevenue,
    totalOutflow,
    payrollTotal,
    largestRevenuePct,
  } = input;

  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const PAGE_W = doc.internal.pageSize.getWidth();
  const PAGE_H = doc.internal.pageSize.getHeight();
  const MARGIN = 48;
  const now = new Date();

  let y = MARGIN;

  // ── HEADER ──────────────────────────────────────────────────────────────────
  doc.setFont('courier', 'bold');
  doc.setFontSize(13);
  doc.text('PRODUCED BY PARITY', MARGIN, y);
  y += 18;

  doc.setFont('courier', 'normal');
  doc.setFontSize(8);
  const truncHash = (snapshot.sha256_hash ?? '').slice(0, 16) + '...';
  doc.text(`Generated: ${isoDate(now)}    Snapshot: ${truncHash}`, MARGIN, y);
  y += 10;

  // thin rule beneath header
  doc.setLineWidth(0.5);
  doc.line(MARGIN, y, PAGE_W - MARGIN, y);
  y += 16;

  // ── DEAL SUMMARY ────────────────────────────────────────────────────────────
  y = sectionHeader(doc, 'DEAL SUMMARY', MARGIN, y);
  y = bodyLine(doc, `Deal ID:                ${deal.id}`, MARGIN, y);
  y = bodyLine(doc, `Deal Name:              ${deal.name ?? '\u2014'}`, MARGIN, y);
  y = bodyLine(doc, `Currency:               ${currency}`, MARGIN, y);
  y = bodyLine(doc, `Transactions:           ${txCount > 0 ? txCount : '\u2014'}`, MARGIN, y);
  y += 6;

  // ── FINANCIAL METRICS ───────────────────────────────────────────────────────
  y = checkPageBreak(doc, y, 120, MARGIN);
  y = sectionHeader(doc, 'FINANCIAL METRICS', MARGIN, y);
  const tierCapped = Boolean(run.tier_capped);
  const missingMonths = Number(run.missing_month_count ?? 0);
  y = bodyLine(doc, `Coverage:               ${fmtBp(run.coverage_pct_bp)}`, MARGIN, y);
  y = bodyLine(doc, `Confidence:             ${fmtBp(run.final_confidence_bp)}`, MARGIN, y);
  y = bodyLine(doc, `Tier:                   ${run.tier}${tierCapped ? ' (capped to Medium \u2014 recon not run)' : ''}`, MARGIN, y);
  y = bodyLine(doc, `Reconciliation:         ${run.reconciliation_status}`, MARGIN, y);
  y = bodyLine(doc, `Missing months:         ${missingMonths}`, MARGIN, y);
  y = bodyLine(doc, `Override count:         ${overridesList.length}`, MARGIN, y);
  y = bodyLine(doc, `Non-transfer total:     ${fmtCents(run.non_transfer_abs_total_cents, currency)}`, MARGIN, y);
  y = bodyLine(doc, `Bank oper. inflow:      ${fmtCents((run.bank_operational_inflow_cents as number) ?? 0, currency)}`, MARGIN, y);
  if (deal.accrual_revenue_cents != null && deal.accrual_revenue_cents > 0) {
    y = bodyLine(doc, `Accrual revenue:        ${fmtCents(deal.accrual_revenue_cents, currency)}`, MARGIN, y);
    const bankInflow = (run.bank_operational_inflow_cents as number) ?? 0;
    const diff = Math.abs((deal.accrual_revenue_cents - bankInflow) / deal.accrual_revenue_cents) * 100;
    y = bodyLine(doc, `Accrual vs bank diff:   ${diff.toFixed(2)}%`, MARGIN, y);
  }
  y += 6;

  // ── ENTITY BREAKDOWN ────────────────────────────────────────────────────────
  y = checkPageBreak(doc, y, 60, MARGIN);
  y = sectionHeader(doc, 'ENTITY BREAKDOWN', MARGIN, y);

  if (entityBreakdown.length > 0) {
    const tableRows = entityBreakdown.map((r) => [
      r.entityName.length > 28 ? r.entityName.slice(0, 27) + '\u2026' : r.entityName,
      r.role,
      fmtCents(r.totalAbsCents, currency),
      r.pctOfTotal.toFixed(1) + '%',
      String(r.txnCount),
    ]);

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [['Entity', 'Role', 'Amount', '% Total', 'Txns']],
      body: tableRows,
      styles: {
        font: 'courier',
        fontSize: 7,
        cellPadding: 3,
        textColor: [0, 0, 0] as [number, number, number],
        lineColor: [0, 0, 0] as [number, number, number],
        lineWidth: 0.3,
        overflow: 'linebreak',
      },
      headStyles: {
        font: 'courier',
        fontStyle: 'bold',
        fontSize: 7,
        fillColor: [255, 255, 255] as [number, number, number],
        textColor: [0, 0, 0] as [number, number, number],
        lineWidth: 0.5,
      },
      alternateRowStyles: {
        fillColor: [255, 255, 255] as [number, number, number],
      },
      columnStyles: {
        0: { cellWidth: 130 },
        1: { cellWidth: 110 },
        2: { cellWidth: 90, halign: 'right' },
        3: { cellWidth: 56, halign: 'right' },
        4: { cellWidth: 40, halign: 'right' },
      },
      theme: 'grid',
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    y = (doc as any).lastAutoTable.finalY + 14;
  } else {
    y = bodyLine(doc, 'No entity breakdown available.', MARGIN, y);
    y += 4;
  }

  // ── CONCENTRATION ───────────────────────────────────────────────────────────
  y = checkPageBreak(doc, y, 60, MARGIN);
  y = sectionHeader(doc, 'CONCENTRATION', MARGIN, y);

  if (topSuppliers.length > 0) {
    y = bodyLine(doc, 'Top suppliers by expense %:', MARGIN, y);
    topSuppliers.forEach((r, i) => {
      const label = r.entityName.length > 30 ? r.entityName.slice(0, 29) + '\u2026' : r.entityName;
      y = bodyLine(doc, `  ${i + 1}. ${label.padEnd(32)} ${r.pctOfTotal.toFixed(1)}%`, MARGIN, y);
    });
  }

  if (topRevenue.length > 0) {
    y += 4;
    y = bodyLine(doc, 'Top revenue entities:', MARGIN, y);
    topRevenue.forEach((r, i) => {
      const label = r.entityName.length > 30 ? r.entityName.slice(0, 29) + '\u2026' : r.entityName;
      y = bodyLine(doc, `  ${i + 1}. ${label.padEnd(32)} ${fmtCents(r.totalAbsCents, currency)}`, MARGIN, y);
    });
  }

  y += 4;
  const payrollPct = totalOutflow > 0 ? ((payrollTotal / totalOutflow) * 100).toFixed(1) : '0.0';
  y = bodyLine(doc, `Payroll % of total outflow:     ${payrollPct}%`, MARGIN, y);
  y = bodyLine(doc, `Largest revenue entity %:       ${largestRevenuePct.toFixed(1)}%`, MARGIN, y);
  y += 6;

  // ── OVERRIDES ───────────────────────────────────────────────────────────────
  y = checkPageBreak(doc, y, 40, MARGIN);
  y = sectionHeader(doc, `OVERRIDES (${overridesList.length})`, MARGIN, y);

  if (overridesList.length === 0) {
    y = bodyLine(doc, 'None applied this session.', MARGIN, y);
  } else {
    for (const ov of overridesList) {
      const entityId = String(ov.entity_id ?? '');
      const ent = entities.find((e) => e.entity_id === entityId);
      const displayName = ent ? ent.display_name : entityId.slice(0, 12) + '\u2026';
      const name = displayName.length > 24 ? displayName.slice(0, 23) + '\u2026' : displayName;
      const line = `  ${name.padEnd(26)} ${String(ov.old_value ?? '?').padEnd(22)} \u2192 ${String(ov.new_value ?? '')}   weight: ${ov.weight}${ov.reason ? `   (${ov.reason})` : ''}`;
      y = bodyLine(doc, line.slice(0, 95), MARGIN, y);
      y = checkPageBreak(doc, y, 14, MARGIN);
    }
  }
  y += 6;

  // ── SNAPSHOT PROVENANCE ─────────────────────────────────────────────────────
  y = checkPageBreak(doc, y, 70, MARGIN);
  y = sectionHeader(doc, 'SNAPSHOT PROVENANCE', MARGIN, y);

  doc.setFont('courier', 'normal');
  doc.setFontSize(7);
  const provLines: [string, string][] = [
    ['snapshot_id:', snapshot.id ?? ''],
    ['sha256_hash:', snapshot.sha256_hash ?? ''],
    ['financial_state_hash:', snapshot.financial_state_hash ?? ''],
  ];
  for (const [label, value] of provLines) {
    y = checkPageBreak(doc, y, 12, MARGIN);
    doc.setFont('courier', 'bold');
    doc.text(label, MARGIN, y);
    doc.setFont('courier', 'normal');
    // indent value on next line if it's too long to fit inline
    const labelW = doc.getTextWidth(label + '  ');
    const availW = PAGE_W - MARGIN * 2 - labelW;
    if (doc.getTextWidth(value) > availW) {
      y += 11;
      y = checkPageBreak(doc, y, 11, MARGIN);
      doc.text(value, MARGIN + 14, y);
    } else {
      doc.text(value, MARGIN + labelW, y);
    }
    y += 11;
  }

  // ── FOOTER ──────────────────────────────────────────────────────────────────
  const totalPages = (doc as jsPDF & { internal: { getNumberOfPages: () => number } }).internal.getNumberOfPages();
  for (let pg = 1; pg <= totalPages; pg++) {
    doc.setPage(pg);
    doc.setLineWidth(0.5);
    doc.line(MARGIN, PAGE_H - 28, PAGE_W - MARGIN, PAGE_H - 28);
    doc.setFont('courier', 'normal');
    doc.setFontSize(6);
    doc.text(
      'This record reflects the committed Parity snapshot as written to the database. Pipeline: v1.',
      MARGIN,
      PAGE_H - 16,
    );
    doc.text(`${pg} / ${totalPages}`, PAGE_W - MARGIN, PAGE_H - 16, { align: 'right' });
  }

  // ── SAVE ────────────────────────────────────────────────────────────────────
  const dateStr = isoDate(now);
  doc.save(`parity-record-${deal.id}-${dateStr}.pdf`);
}

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

export interface MonthlyCashflowRow {
  month: string;
  inflow_cents: number;
  outflow_cents: number;
  net_cents: number;
  mom_change_bps: number | null;
  mom_reliable: boolean;
}

export interface CreditScoringInputs {
  average_monthly_inflow_cents: number;
  median_monthly_inflow_cents: number;
  average_monthly_outflow_cents: number;
  average_net_monthly_cents: number;
  peak_net_position_cents: number;
  trough_net_position_cents: number;
  revenue_growth_bps: number;
  loan_repayment_burden_bps: number;
  payroll_stability: string;
  payroll_months_detected: number;
  kra_compliance: string;
  kra_note: string;
  tax_total_cents: number;
  statement_months: number;
  month_count_with_inflow: number;
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
  monthlyCashflow?: MonthlyCashflowRow[];
  creditScoringInputs?: CreditScoringInputs;
  monthlyEntityBreakdown?: Array<Record<string, unknown>>;
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
    monthlyCashflow,
    creditScoringInputs,
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

  // ── CREDIT SCORING INPUTS ───────────────────────────────────────────────────
  if (creditScoringInputs) {
    y = sectionHeader(doc, '01  CREDIT SCORING INPUTS', MARGIN, y);

    const csiRows: [string, string, string][] = [
      ['Average Monthly Inflow', fmtCents(creditScoringInputs.average_monthly_inflow_cents, currency), `${creditScoringInputs.month_count_with_inflow}-month arithmetic mean`],
      ['Median Monthly Inflow', fmtCents(creditScoringInputs.median_monthly_inflow_cents, currency), `${creditScoringInputs.month_count_with_inflow}-month median`],
      ['Average Monthly Outflow', fmtCents(creditScoringInputs.average_monthly_outflow_cents, currency), '12-month arithmetic mean'],
      ['Average Net Monthly Position', fmtCents(creditScoringInputs.average_net_monthly_cents, currency), 'Inflow minus outflow mean'],
      ['Peak Net Position', fmtCents(creditScoringInputs.peak_net_position_cents, currency), 'Best single month'],
      ['Trough Net Position', fmtCents(creditScoringInputs.trough_net_position_cents, currency), 'Worst single month'],
      ['Revenue Growth', (creditScoringInputs.revenue_growth_bps >= 0 ? '+' : '') + (creditScoringInputs.revenue_growth_bps / 100).toFixed(1) + '%', 'First vs last month with inflow'],
      ['Loan Repayment Burden', (creditScoringInputs.loan_repayment_burden_bps / 100).toFixed(1) + '%', '% of total outflows'],
      ['Payroll Stability', creditScoringInputs.payroll_stability, `${creditScoringInputs.payroll_months_detected} months detected`],
      ['KRA Compliance', creditScoringInputs.kra_compliance, creditScoringInputs.kra_note],
    ];

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [['Scoring Metric', 'Value', 'Basis']],
      body: csiRows,
      styles: {
        font: 'courier',
        fontSize: 7,
        cellPadding: 3,
        textColor: [0, 0, 0] as [number, number, number],
        lineColor: [0, 0, 0] as [number, number, number],
        lineWidth: 0.3,
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
        0: { cellWidth: 160 },
        1: { cellWidth: 120, halign: 'right' },
        2: { cellWidth: 200 },
      },
      theme: 'grid',
    });

    y = (doc as any).lastAutoTable.finalY + 20;
  }

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

  // ── MONTHLY ENTITY BREAKDOWN ────────────────────────────────────────────────
  if ((monthlyCashflow && monthlyCashflow.length > 0) && (input as any).monthlyEntityBreakdown) {
    const breakdown = (input as any).monthlyEntityBreakdown as Array<{
      month: string;
      revenue_in_cents: number;
      suppliers_cents: number;
      payroll_cents: number;
      loan_repayment_cents: number;
      tax_cents: number;
    }>;
    if (breakdown.length > 0) {
      y = checkPageBreak(doc, y, 60, MARGIN);
      y = sectionHeader(doc, '03  MONTHLY ENTITY BREAKDOWN', MARGIN, y);

      const breakdownRows = breakdown.map((row) => [
        row.month,
        fmtCents(row.revenue_in_cents, currency),
        fmtCents(row.suppliers_cents, currency),
        row.payroll_cents > 0 ? fmtCents(row.payroll_cents, currency) : '—',
        row.loan_repayment_cents > 0 ? fmtCents(row.loan_repayment_cents, currency) : '—',
        row.tax_cents > 0 ? fmtCents(row.tax_cents, currency) : '—',
      ]);

      autoTable(doc, {
        startY: y,
        margin: { left: MARGIN, right: MARGIN },
        head: [['Month', 'Revenue In', 'Suppliers', 'Payroll', 'Loan Repmt', 'Tax']],
        body: breakdownRows,
        styles: {
          font: 'courier',
          fontSize: 7,
          cellPadding: 3,
          textColor: [0, 0, 0] as [number, number, number],
          lineColor: [0, 0, 0] as [number, number, number],
          lineWidth: 0.3,
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
          0: { cellWidth: 60 },
          1: { cellWidth: 95, halign: 'right' },
          2: { cellWidth: 95, halign: 'right' },
          3: { cellWidth: 80, halign: 'right' },
          4: { cellWidth: 80, halign: 'right' },
          5: { cellWidth: 86, halign: 'right' },
        },
        theme: 'grid',
      });

      y = (doc as any).lastAutoTable.finalY + 14;
    }
  }

  // ── ITEMS REQUIRING REVIEW ──────────────────────────────────────────────────
  const needsReviewEntities = entityBreakdown.filter(
    (r) => r.role === 'needs_review' || r.role === 'capital_injection' || r.role === 'loan_inflow'
  );
  if (needsReviewEntities.length > 0) {
    y = checkPageBreak(doc, y, 60, MARGIN);
    y = sectionHeader(doc, 'ITEMS REQUIRING REVIEW', MARGIN, y);
    y = bodyLine(doc, `${needsReviewEntities.length} transaction${needsReviewEntities.length > 1 ? 's' : ''} flagged for analyst review before finalising this record.`, MARGIN, y);
    y += 4;

    const reviewRows = needsReviewEntities.map((r) => {
      const label = r.entityName.length > 32 ? r.entityName.slice(0, 31) + '\u2026' : r.entityName;
      const action =
        r.role === 'loan_inflow' ? 'VERIFY — possible loan disbursement'
        : r.role === 'capital_injection' ? 'VERIFY — possible capital injection'
        : 'CLASSIFY — large or unidentified inflow/outflow';
      return [label, r.role, fmtCents(r.totalAbsCents, currency), action];
    });

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [['Entity', 'Flagged As', 'Amount', 'Action Required']],
      body: reviewRows,
      styles: {
        font: 'courier',
        fontSize: 7,
        cellPadding: 3,
        textColor: [0, 0, 0] as [number, number, number],
        lineColor: [0, 0, 0] as [number, number, number],
        lineWidth: 0.3,
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
        0: { cellWidth: 140 },
        1: { cellWidth: 90 },
        2: { cellWidth: 90, halign: 'right' },
        3: { cellWidth: 176 },
      },
      theme: 'grid',
    });

    y = (doc as any).lastAutoTable.finalY + 14;
  }

  // ── MONTHLY CASHFLOW ────────────────────────────────────────────────────────
  if (monthlyCashflow && monthlyCashflow.length > 0) {
    y = checkPageBreak(doc, y, 60, MARGIN);
    y = sectionHeader(doc, 'MONTHLY CASHFLOW & CASH FLOW HABITS', MARGIN, y);

    let hasUnreliable = false;
    const cashflowRows = monthlyCashflow.map((m) => {
      let momDisplay: string;
      if (m.mom_change_bps === null || m.month === monthlyCashflow[0].month) {
        momDisplay = '—';
      } else if (!m.mom_reliable) {
        hasUnreliable = true;
        momDisplay = (m.mom_change_bps >= 0 ? '+' : '') + (m.mom_change_bps / 100).toFixed(1) + '%*';
      } else {
        momDisplay = (m.mom_change_bps >= 0 ? '+' : '') + (m.mom_change_bps / 100).toFixed(1) + '%';
      }
      return [
        m.month,
        fmtCents(m.inflow_cents, currency),
        fmtCents(m.outflow_cents, currency),
        fmtCents(m.net_cents, currency),
        momDisplay,
      ];
    });

    autoTable(doc, {
      startY: y,
      margin: { left: MARGIN, right: MARGIN },
      head: [['Month', 'Inflow', 'Outflow', 'Net Position', 'MoM Change']],
      body: cashflowRows,
      styles: {
        font: 'courier',
        fontSize: 7,
        cellPadding: 3,
        textColor: [0, 0, 0] as [number, number, number],
        lineColor: [0, 0, 0] as [number, number, number],
        lineWidth: 0.3,
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
        0: { cellWidth: 70 },
        1: { cellWidth: 110, halign: 'right' },
        2: { cellWidth: 110, halign: 'right' },
        3: { cellWidth: 110, halign: 'right' },
        4: { cellWidth: 80, halign: 'right' },
      },
      theme: 'grid',
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    y = (doc as any).lastAutoTable.finalY + 14;
  }

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

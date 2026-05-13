import { NextRequest, NextResponse } from 'next/server';
import { Resend } from 'resend';

const NOTIFY_EMAIL = 'mbakayaweever@gmail.com';

/**
 * POST /api/request-parser
 *
 * Accepts JSON (from the in-app modal) or multipart FormData (from /parsers/request page).
 *
 * JSON body:
 *   { bank_name, country, account_type, notes?, deal_id?, document_id?, original_filename?, contact_email? }
 *
 * FormData:
 *   bank_name, contact_email, notes?, sample_file? (File)
 */
export async function POST(request: NextRequest) {
  const resend = new Resend(process.env.RESEND_API_KEY);
  try {
    const contentType = request.headers.get('content-type') ?? '';
    let bankName = '';
    let contactEmail = '';
    let notes = '';
    let country = '';
    let accountType = '';
    let dealId = '';
    let documentId = '';
    let originalFilename = '';
    let fileBuffer: ArrayBuffer | null = null;
    let fileName = '';

    // ── Parse body ────────────────────────────────────────────────────────────
    if (contentType.includes('multipart/form-data')) {
      const form = await request.formData();
      bankName = (form.get('bank_name') as string) ?? '';
      contactEmail = (form.get('contact_email') as string) ?? '';
      notes = (form.get('notes') as string) ?? '';
      country = (form.get('country') as string) ?? '';
      accountType = (form.get('account_type') as string) ?? '';
      const sampleFile = form.get('sample_file') as File | null;
      if (sampleFile) {
        fileBuffer = await sampleFile.arrayBuffer();
        fileName = sampleFile.name;
      }
    } else {
      // JSON
      const body = (await request.json()) as Record<string, string>;
      bankName = body.bank_name ?? '';
      contactEmail = body.contact_email ?? '';
      notes = body.notes ?? '';
      country = body.country ?? '';
      accountType = body.account_type ?? '';
      dealId = body.deal_id ?? '';
      documentId = body.document_id ?? '';
      originalFilename = body.original_filename ?? '';
    }

    if (!bankName) {
      return NextResponse.json({ error: 'bank_name is required' }, { status: 400 });
    }

    // ── Build notification email HTML ─────────────────────────────────────────
    const notifyHtml = `
      <h2 style="font-family:monospace;color:#6366F1">🔧 Parser Request: ${bankName}</h2>
      <table style="font-family:sans-serif;font-size:14px;border-collapse:collapse">
        <tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Bank</td><td>${bankName}</td></tr>
        ${country ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Country</td><td>${country}</td></tr>` : ''}
        ${accountType ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Account type</td><td>${accountType}</td></tr>` : ''}
        ${contactEmail ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Contact</td><td>${contactEmail}</td></tr>` : ''}
        ${dealId ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Deal ID</td><td style="font-family:monospace">${dealId}</td></tr>` : ''}
        ${documentId ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">Document ID</td><td style="font-family:monospace">${documentId}</td></tr>` : ''}
        ${(originalFilename || fileName) ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600">File</td><td style="font-family:monospace">${originalFilename || fileName}</td></tr>` : ''}
        ${notes ? `<tr><td style="padding:4px 12px 4px 0;color:#6b7280;font-weight:600;vertical-align:top">Notes</td><td>${notes}</td></tr>` : ''}
      </table>
      <hr style="margin:20px 0;border:none;border-top:1px solid #e5e7eb"/>
      <p style="font-family:monospace;font-size:12px;color:#9ca3af">
        Build parser following equity_extractor.py pattern.<br/>
        Deploy: <code>gcloud run deploy parity-ingestion --source .</code>
      </p>
    `;

    // ── Attachments (if file was uploaded) ────────────────────────────────────
    const attachments =
      fileBuffer && fileName
        ? [{ filename: fileName, content: Buffer.from(fileBuffer).toString('base64') }]
        : [];

    // ── Send notification to yourself ─────────────────────────────────────────
    const bankSlug = bankName.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40);
    await resend.emails.send({
      from: 'Parity Parser Requests <onboarding@resend.dev>',
      to: [NOTIFY_EMAIL],
      subject: `🔧 Parser Request: ${bankName}`,
      html: notifyHtml,
      ...(attachments.length > 0 ? { attachments } : {}),
    });

    // ── Send confirmation to requester (if email provided) ────────────────────
    if (contactEmail) {
      await resend.emails.send({
        from: 'Parity <onboarding@resend.dev>',
        to: [contactEmail],
        subject: 'Parser Request Received — Parity',
        html: `
          <h2 style="font-family:monospace;color:#6366F1">Parser Request Received</h2>
          <p style="font-family:sans-serif;font-size:14px">
            Thanks! We're building a custom parser for <strong>${bankName}</strong>.
          </p>
          <p style="font-family:sans-serif;font-size:14px">
            <strong>Typical turnaround:</strong> 4–7 hours.<br/>
            We'll email you at ${contactEmail} when the parser is ready so you can re-run your analysis.
          </p>
          <hr style="margin:20px 0;border:none;border-top:1px solid #e5e7eb"/>
          <p style="font-family:sans-serif;font-size:12px;color:#9ca3af">Questions? Reply to this email.</p>
        `,
      });
    }

    return NextResponse.json({ success: true, bank_slug: bankSlug });
  } catch (error) {
    console.error('[api/request-parser] error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to submit parser request' },
      { status: 500 }
    );
  }
}

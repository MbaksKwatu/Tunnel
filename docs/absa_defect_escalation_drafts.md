# Parser Reconciliation Defects — Drafts for Review

*Originally scoped to ABSA only; expanded 2026-06-21 once a cross-extractor
check showed the picture was broader (and, on closer trace, narrower than the
raw fail-count suggested — most "failures" were a harness limitation, not
real bugs). Three real defects confirmed: ABSA, KCB, Stanbic. Two non-bugs
ruled out: Equity_CLMS, MPESA_PDF.*

***All five tickets below are now filed in Linear** (team Parityafrica,
assignee Sam): [PAR-24](https://linear.app/parityafrica/issue/PAR-24)
(ABSA, Medium), [PAR-25](https://linear.app/parityafrica/issue/PAR-25)
(Stanbic, Medium), [PAR-27](https://linear.app/parityafrica/issue/PAR-27)
(telemetry gap, Medium), [PAR-28](https://linear.app/parityafrica/issue/PAR-28)
(harness limitation, Low) — all still Backlog, not yet fixed.*

***[PAR-26](https://linear.app/parityafrica/issue/PAR-26) (KCB, High) — fix
landed 2026-06-21, status In Progress.** Root cause precisely confirmed: the
last page of a KCB statement carries a totals row (aggregate money-out/
money-in/balance for the whole statement) immediately after the "Balance at
Period End" footer text; the old skip-check only looked at description text
and never matched (the totals row has no description, and the footer phrase
itself is fragmented across row-groups by pdfplumber). Fixed in
`kcb_extractor.py` by tracking when the footer section starts and skipping
everything after it on that page, rather than trying to match the totals row
itself. Verified: `balance_reconciliation` now passes on the real fixture; a
new regression test confirmed (via `git stash`) to fail without the fix and
pass with it; KCB_Online unaffected; full related suite 37 passed/3 skipped/
0 failed. **Not yet merged or staged** — still needs PR review and the
storage-level historical-impact check before being called fully closed.*

---

## 1. How blast radius was actually checked (not the original query)

The originally drafted SQL (`WHERE extraction_method = 'ABSA'`) could not
answer this safely as written:

1. No column anywhere records which extractor processed a document —
   `pds_deals.extraction_method`/`source_bank` doesn't exist, and
   `pds_documents.analytics.extractor_type` is `null` on every document in
   production.
2. Even with that fixed, `pds_raw_transactions` (backend's post-ingestion
   format) wouldn't show ABSA's phantom-row signature — `_parity_result_to_
   rows()` drops rows lacking a parseable date before insert. A query keyed
   on raw row shape gives a false-clean result on affected data.

**Actual method:** `pds_documents.storage_url` retains original upload
filenames (`inline://<filename>`). Traced all 88 production documents and
all 20 sealed snapshots' source files by filename and, where filenames were
ambiguous (`musa_doc_N.pdf`), by content (transaction description style).

---

## 2. What's confirmed real, per extractor

| Extractor | Defect | Blast radius | Status |
|---|---|---|---|
| **ABSA** | Phantom mid-statement rows (date='', description='', debit present, balance='') break reconciliation ~20+ points/statement | **Zero — confirmed.** No filename/content match across 88 documents or 20 snapshots. | Ready to fix, not urgent. |
| **Stanbic** | ~30% of rows have both debit and credit empty while balance still changes — amount not captured, money's moving but unrecorded | **Zero — confirmed.** Same method, same result: no match anywhere. | Ready to fix, not urgent. |
| **KCB** | One footer line ("...Custom BALANCE AT PERIOD END:") merges into the last transaction row, picking up a stray credit amount from footer text | **CHECKED 2026-06-21 — NOT zero, structurally likely on every statement.** 12 completed KCB documents and at least 8 distinct deals/snapshots in production (vs. zero for ABSA/Stanbic) — confirmed via `pds_documents.storage_url`. The merged footer text ("BALANCE AT PERIOD END") is standard KCB statement boilerplate, not a one-off fixture artifact — confirmed by reproducing it independently on a second real KCB fixture. The row-merge mechanism is deterministic, not PDF-jitter-dependent like ABSA's. **This means the defect most likely fired on every one of the 12 completed documents, not a fraction of them.** Could not get literal per-document confirmation — the actual production PDF bytes live in Supabase Storage, not in any table queryable here; would need either a storage-download tool or for someone with access to re-run `run_parser_harness()` against the actual stored files. |
| **COOP** | Detection mismatch — committed test fixture returns `UNSUPPORTED_FORMAT` against the live `detect_coop()` | Zero recent attempts, either way — no filename/company-name match for Co-op/Cooperative anywhere in production. Not urgent (nobody's affected today), not verified-working either. | Fix whenever, not a fire. |
| Equity_CLMS | N/A — **not a bug.** The 2 "breaks" found are legitimate account-boundary balance resets in a multi-account statement; the harness wrongly assumes one continuous chain. | N/A | No extractor fix needed. |
| MPESA_PDF | N/A — **not a bug.** 8,334 of 8,485 rows "broke" because M-Pesa's interleaved transaction types (transfers, paybill charges, agent deposits) don't form one sequential ledger; the harness's check doesn't fit this format. | N/A | No extractor fix needed. |
| NCBA | Unknown | Unchecked | No fixture exists anywhere — needs a sample before anything can be assessed. |

---

## 3. Escalation message — rewritten, KCB is now the headline, not a footnote

**To:** Weever, Tom
**Subject:** KCB extractor likely affects every processed statement — needs a look before anything else here

While verifying the new parser-config interface, the deterministic harness
caught reconciliation defects in three live extractors: `absa_extractor.py`,
`stanbic_extractor.py`, and `kcb_extractor.py`. Two other apparent failures
(Equity_CLMS, MPESA_PDF) turned out to be the harness's own checking logic
breaking on multi-account statements and M-Pesa's non-sequential transaction
shape respectively — not real bugs, no action needed there.

**ABSA and Stanbic: confirmed zero production impact.** Traced directly via
document filenames and content across all 88 production documents and all
20 sealed snapshots — neither extractor has ever actually been used in
production. Filing both as normal-priority bugs, fix before the parser
pipeline brings either into active use.

**KCB is the one that needs your attention.** Unlike ABSA/Stanbic, KCB is in
active production use — 12 completed documents, at least 8 distinct
deals/snapshots. Its defect: the statement's closing "BALANCE AT PERIOD
END" line gets merged into the last transaction row, picking up a stray
credit amount from that footer text. I confirmed this isn't one fixture's
quirk — that footer phrase is standard KCB statement boilerplate, and the
row-merge that swallows it is deterministic, not dependent on PDF
formatting luck the way ABSA's bug was. That means it most likely fired on
every one of those 12 documents, not a fraction of them.

I could not get a literal per-document confirmation — the actual production
PDFs are in Supabase Storage, which I don't have a tool to pull from here.
Someone with storage access needs to either re-run `run_parser_harness()`
against the actual stored KCB files, or pull a few and eyeball the last
transaction row, to confirm exactly which delivered snapshots have an
inflated final-row credit. That result determines whether any already-sent
GBFund/customer deliverable needs a correction — please don't treat this as
settled until that check happens.

---

## 4. Tickets — three real bugs, split by root cause since they're unrelated

### Ticket A — ABSA phantom rows

**Title:** ABSA extractor: phantom rows break balance reconciliation (~20+ points/statement)
**Severity:** Medium — confirmed zero production impact. Fix before the parser-pipeline's ABSA pilot brings it into active use.
**Description:** `absa_extractor.py`'s row-grouping produces orphaned `RawTransaction` rows: `date=''`, `description=''`, a debit amount present, `balance=''`. Breaks running-balance reconciliation at each occurrence, ~20+ per statement. Confirmed identical on the bespoke extractor and the new config-driven path (`layout_config.py`) — pre-existing, not introduced by either.
**Suspected root cause:** PDF baseline jitter splitting one transaction's amount into its own visual-line bucket during row-grouping. `LayoutConfig.row_tolerance` (currently `5.0`) is a plausible lever — unconfirmed.
**Reproduction:** `run_parser_harness()` against any real ABSA statement — `balance_reconciliation` fails, citing break-point rows.
**Blocked on:** nothing.

### Ticket B — Stanbic uncaptured amounts

**Title:** Stanbic extractor: debit/credit amount not captured for ~30% of rows despite balance changing
**Severity:** Medium — confirmed zero production impact, but the underlying defect is more serious in kind than ABSA's (data is lost, not just split across rows). Fix before Stanbic comes into active use.
**Description:** In `stanbic_extractor.py`, ~30% of extracted rows show both `debit_raw` and `credit_raw` empty while the running balance still changes between rows — meaning a transaction happened but its amount and direction (debit vs credit) were never captured. Possibly compounded by a multi-account/section-restart pattern (one row found mid-statement reading `'BALANCE BROUGHT FORWARD'` with `date=''`, suggesting Stanbic statements may also span multiple accounts the way Equity_CLMS does — worth checking whether all 107 breaks are this amount-capture bug or whether some are legitimate account-boundary resets like Equity_CLMS's, before scoping the fix).
**Reproduction:** `run_parser_harness()` against `tests/fixtures/stanbic_zuridi.pdf` — `balance_reconciliation` fails on ~107 of 355 rows.
**Blocked on:** nothing for filing; the fix itself should disambiguate amount-capture failures from legitimate account boundaries before changing extraction logic.

### Ticket C — KCB footer-line merge, every processed statement — HIGH, ready to file

**Title:** KCB extractor: closing-balance footer line merges into last transaction row, inflating final credit on (most likely) every statement processed
**Severity:** High — not because the per-occurrence defect is large (one stray credit amount, once, at the end of a statement), but because of scope: KCB is the most-used extractor in production (12 completed documents, 8+ deals/snapshots) and the merge mechanism is deterministic boilerplate-text matching, not PDF-formatting luck. Reproduced independently on a second real KCB fixture. Most likely affects every completed KCB document to date, not a fraction.
**What's NOT yet confirmed:** exact per-snapshot impact. Could not pull the actual production PDF bytes from Supabase Storage from this environment — needs someone with storage access to re-run extraction against the real stored files (or spot-check a few) and confirm which delivered snapshots have an inflated final-row credit.
**Description:** `kcb_extractor.py`'s row-merging logic absorbs the statement's closing "...Custom BALANCE AT PERIOD END:" line into the last real transaction row, picking up a stray credit amount from that footer text and breaking reconciliation at that one point. Confirmed on two independent real KCB statements.
**Reproduction:** `run_parser_harness()` against any real KCB fixture — single break at the final row, footer text visible in `description`.
**Blocked on:** nothing for filing. The storage-access check above should happen in parallel, not gate filing this ticket — the fix itself (exclude the closing-balance line from row-merging, same kind of footer-skip-phrase pattern already used in `layout_config.py`'s ABSA config) can proceed independently of confirming exact historical impact.

### Ticket D — telemetry gap (unaffected by any of the above, file as-is)

**Title:** `pds_documents` has no record of which extractor/bank processed a file — blocks blast-radius checks for any future parser defect
**Severity:** Low-medium, high leverage.
**Description:** Investigating these defects required manual filename/content tracing across 88 documents because no column records which extractor processed a file — `pds_deals.extraction_method`/`source_bank` doesn't exist, `pds_documents.analytics.extractor_type` is `null` on every document. The extraction code already knows which extractor it used; this is a matter of persisting that.
**Recommendation:** populate `extractor_type`/`source_bank` on `pds_documents` at ingestion time. Sequence alongside Phase 2's `commit_hash` tracking — same underlying need.
**Blocked on:** nothing.

### Ticket E — harness reconciliation check assumes one continuous balance chain (new, lower priority)

**Title:** `run_parser_harness()`'s balance_reconciliation check produces false failures on multi-account statements and non-sequential-ledger formats
**Severity:** Low priority now, but real — fix before Phase 3's agent-build-loop starts trusting this harness as an automated gate on new banks.
**Description:** The check assumes a single continuous running-balance chain across an entire statement. This breaks on (a) multi-account statements where the balance legitimately resets at an account boundary (confirmed on Equity_CLMS, 2 false breaks out of 10,891 rows) and (b) non-sequential-ledger formats like M-Pesa, where transaction types don't form one simple chain at all (confirmed on MPESA_PDF, 8,334 of 8,485 rows falsely flagged). If Phase 3's agent hits either shape on a future bank, it will get this same false signal — and an agent iterating against a false failure could "fix" a parser that was never broken.
**Two plausible directions, not decided:** (1) detect account-boundary resets (e.g., via date discontinuities or an explicit account-number field) and validate each segment independently, or (2) report `'skipped'` (extending the existing semantics — inapplicable, not failed) when the chain-continuity assumption can't be verified, rather than reporting `False`.
**Blocked on:** nothing — doesn't block Tickets A/B/C, but should land before Phase 3 work starts.

---

## 5. Status: what's left before this file is fully actionable

- [x] ABSA blast radius — confirmed zero
- [x] Stanbic blast radius — confirmed zero
- [x] **KCB blast radius — run.** Result: NOT zero, structurally likely on
      every processed statement (12 completed documents, 8+ deals/snapshots).
      Ticket C and the escalation email above reflect this.
- [ ] **Remaining gap: per-document confirmation against actual production
      PDF bytes**, which live in Supabase Storage and aren't reachable from
      this environment. Needs someone with storage access to close this —
      the deterministic-mechanism argument is strong evidence but isn't the
      same as literally re-running extraction on the 12 real files.
- [ ] COOP — confirmed zero current usage, severity/fix timing still a
      product call, not blocked on anything technical
- [ ] NCBA — needs a fixture before any of this applies

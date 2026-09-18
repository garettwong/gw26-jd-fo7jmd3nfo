# Private salary cash-flow refresh

The existing `earnings/` link remains the private entry point. Decryption uses
the existing device key; no salary navigation/key is added to the public timetable.

## Sources and refresh

- The latest immutable timetable version supplies teaching hours and full-course
  completion dates through `generate_earnings.py`.
- `salary_cashflow.py` reconciles the local invoice delivery register. The register
  remains outside this repository. Only sanitized payment states enter encrypted
  salary payloads; do not commit the register or plaintext salary exports.
- Run `generate_earnings.py --latest-only` after a verified record change. This
  preserves historical snapshots and writes both latest and root encrypted payloads.
- Update the register's reconciliation totals and evidence timestamp only after
  actual verification. Never manufacture freshness from the generator run time.
- The existing completed-course invoice automation includes this refresh and
  publication step. It runs on its established course-completion dates, not as a
  live bank-account feed.

## Payment ledger layout

The 2026-09-18 user request supersedes earlier forecast and purchase-planner requirements. Remove the N-day forecast and spending calculator entirely. Show all records by default, with filters for received, submitted unpaid, and unfinished/unsubmitted work.

Every payment card must use the same four-row table: (1) full-class end date (service end for non-course jobs), (2) actual invoice submission date, (3) estimated receipt date with its basis, (4) actual receipt date. Unknown dates stay explicitly unknown. Never substitute invoice-face dates for submission dates or estimates for actual receipts. Retain paid records in the all/paid views.

For Calvin invoices, use actual submission plus 21 calendar days when known, including paid records. Without submission evidence, any future-course estimate must explicitly assume completion and immediate submission. No date is a guaranteed deadline.

Separate overview totals into received money, submitted invoices still unpaid, and unfinished/unsubmitted work. Show the total scheduled-pay arithmetic secondarily; do not describe future-course income as an overdue invoice or bank balance. Keep public timetable and private salary selectors synchronized; receipt-only changes refresh the latest salary snapshot without creating an unrelated timetable release.

## Release checks

1. Reconcile each completed course amount to the register; block discrepancies.
2. Verify received + unreceived equals total scheduled pay without double counting.
3. Test invoice-ready, submitted-date-known, submitted-date-unknown, future course,
   received, overdue, stale-source and no-date states.
4. Test a Hong Kong date rollover and all four date fields, including unknown dates.
5. Inspect phone and desktop output. Keep the existing private URL/key and ensure
   salary/timetable selectors have matching latest IDs.
6. Commit only intended source files to `main`, preserving unrelated changes.
   Publication is separate: fetch `origin/gh-pages`, use a clean isolated worktree
   from that ref, and promote only generated `earnings/` files. Push the resulting
   commit to `gh-pages` without forcing. Dispatch `deploy-pages.yml` on `main`
   (`gh workflow run deploy-pages.yml --ref main`); its checkout uses `gh-pages`.
   A source push alone does not deploy this site. Wait for deployment and verify
   the actual old private link and encrypted payload before reporting success.

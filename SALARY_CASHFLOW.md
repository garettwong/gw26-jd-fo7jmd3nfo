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

## Cash-flow semantics

The top panel always uses confirmed work, independently of the historical salary
mode buttons below. One selectable N-day total (presets or 1-365 custom days)
is cumulative from today to the displayed end date and excludes paid
items, estimates whose dates have passed, and prepared invoices with no confirmed
client submission. No row becomes paid because its expected date passed.

Use submission date plus 21 calendar days as a conservative Calvin planning
assumption, not a contractual guarantee. If only a user confirmation date exists,
show that proxy explicitly. Future courses assume completion and immediate
submission. After completion, a still-unissued row is removed from the top forecast
until the invoice record is updated. SEN retains the existing month-end plus
seven-day assumption. Other-job received records retain their prior evidence.

The browser computes today's date in Hong Kong, warns when payment evidence is
older than seven days, and refreshes the forecast after a date change. Reloading
fetches encrypted records without using the browser cache.

Each payment card has separate actual client-submission date, actual receipt date,
and expected receipt date fields. Never substitute invoice-face dates, self-email
dates or confirmation dates for actual client submission. Unknown dates remain
explicitly unknown, even for already-paid invoices. All records, received,
unreceived and action-needed items are available through the ledger filter.

Keep the all-record unreceived total permanently visible, separately from the
N-day forecast; show total scheduled pay minus confirmed received pay and split
unreceived amounts into submitted invoices and unfinished courses. Default the
ledger to all unreceived records, not only the short-term forecast. Keep the course
name and amount visible, with stage-specific rows: before submission show whole-class
start, whole-class end, and submit-after-final-lesson date; after submission show
actual client-submission date/time and expected receipt date; paid records show
submission and actual receipt dates. Keep invoice-face dates and secondary estimates
in expandable details. Do not repeat blank/not-issued/not-received rows on future
course cards. Whole-class dates must come from the matching payment context, not
Garett's personal service period. Existing total and spending calculations remain
independent of card presentation.
Historical salary HTML must carry a clear historical-snapshot warning and link to
the current salary entry point. Do not rewrite historical encrypted data.

The purchase calculator stores inputs only in browser localStorage. It shows both
cash-only and forecast-inclusive margins above a user-defined safety cushion. It
requires current balance, purchase price, N-day living expenses and a separate
minimum savings cushion. Changing N clears the living-expense input so a shorter
period's costs cannot silently be reused for a longer period. It is not a bank
balance or promise of affordability. Local inputs do not sync between devices.

## Release checks

1. Reconcile each completed course amount to the register; block discrepancies.
2. Verify received + unreceived equals total scheduled pay without double counting.
3. Test invoice-ready, submitted-date-known, submitted-date-unknown, future course,
   received, overdue, stale-source and no-date states.
4. Test a Hong Kong date rollover and purchase arithmetic, including blank inputs.
5. Inspect phone and desktop output. Keep the existing private URL/key and ensure
   salary/timetable selectors have matching latest IDs.
6. Commit only intended source files to `main`, preserving unrelated changes.
   Publication is separate: fetch `origin/gh-pages`, use a clean isolated worktree
   from that ref, and promote only generated `earnings/` files. Push the resulting
   commit to `gh-pages` without forcing. Dispatch `deploy-pages.yml` on `main`
   (`gh workflow run deploy-pages.yml --ref main`); its checkout uses `gh-pages`.
   A source push alone does not deploy this site. Wait for deployment and verify
   the actual old private link and encrypted payload before reporting success.

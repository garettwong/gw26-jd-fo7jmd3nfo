# V20y Requirement Ledger

## Release identity

- Baseline public/private release: `2026-08-25-V20x`.
- Baseline timetable build: `v20x-auto-cross-device-lesson-log-20260825a`.
- New non-destructive release: `2026-08-25-V20y`.
- New timetable build: `v20y-hk239-city-dec-first-lesson-marker-20260825a`.
- Public and private salary selectors must both promote the same V20y ID.
- V20x and all older public/private snapshots must remain byte-for-byte unchanged.

## Authoritative change

- Course/cohort: `HK239HG`, Class `城市一條龍`, Christian Action Choi Wan.
- Status: confirmed.
- Teacher/ownership: Garett for all six lessons.
- Teaching room: `102` for all six lessons.
- Remove the six old lessons on 2026-11-11 through 2026-11-13; do not retain duplicates.
- Add the following six replacement lessons in Asia/Shanghai/Hong Kong local time:

| Lesson | Date | Weekday | Time | Teaching hours | Required note |
| --- | --- | --- | --- | ---: | --- |
| L1 | 2026-12-16 | Wednesday | 09:00-12:00 | 3 | None |
| L2 | 2026-12-16 | Wednesday | 13:00-16:00 | 3 | None |
| L3 | 2026-12-17 | Thursday | 09:00-12:00 | 3 | None |
| L4 | 2026-12-17 | Thursday | 13:00-16:00 | 3 | None |
| L5 | 2026-12-18 | Friday | 09:00-12:00 | 3 | 持續評估／小組討論／專題報告 |
| L6 | 2026-12-18 | Friday | 13:00-16:00 | 3 | 期末考試 15:30-16:30 |

## Deterministic arithmetic

- Six blocks x 3 teaching hours = 18 teaching hours.
- Each day has 09:00-12:00 plus 13:00-16:00 = 6 teaching hours.
- Each day has a 12:00-13:00 intended meal gap = 1 elapsed non-teaching hour.
- Three days x 7 elapsed hours = 21 elapsed hours; 21 elapsed minus 3 meal hours = 18 teaching hours.
- Salary rate remains HKD 300/hour; 18 hours x HKD 300 = HKD 5,400.
- November loses 18 hours/HKD 5,400; December gains 18 hours/HKD 5,400.
- Confirmed and confirmed-plus-unconfirmed grand totals must remain unchanged from V20x.
- Counted salary-entry totals must remain unchanged from V20x.

## First-lesson marker

- Every ERB cohort, including Christian Action and Methodist ERB cohorts, must have exactly one marked first lesson.
- Marker text must be conspicuous Traditional Chinese: `此班第一堂`.
- The marker must appear in each first lesson card in calendar grid and mobile agenda rendering.
- The marker must remain legible without overlap at desktop 2560x1440 and mobile 390x844 viewports.
- YMCA, DGS, holidays, school entries, Mike Sir entries, cancelled entries, and proposal-only entries must not receive this ERB marker.

## Preservation and compatibility

- Do not edit or overwrite the source workbook or supplied/user evidence.
- Record the new instruction in the supplemental confirmed source metadata.
- Preserve all unrelated timetable and class-context rows.
- Preserve the V20x automatic cross-device lesson-log code and activation flow.
- Preserve all pre-V20y lesson-log keys for unchanged lessons.
- Do not expose the private salary key in tracked files, logs, URLs reported to the user, or screenshots.

## Release gates

- Verify exact old-row removal, exact new-row insertion, dates/weekdays, lesson sequence, times, durations, room, teacher, status, notes, no overlap, meal gap, and no other current commitment on the three new dates.
- Verify public/private selector parity, one latest item, matching V20y salary snapshot, successful AES-GCM decryption, and salary month transfer with unchanged total.
- Verify all non-target source events/context rows and all historical V20x public/private snapshot hashes are unchanged.
- Run Playwright functional and visual QA on desktop and mobile, including first-lesson coverage, the moved cohort, room 102, old-date absence, selector navigation, salary report, console/page errors, overflow, and overlap.
- Commit source release, copy only published artifacts to the deployment worktree, commit deployment, push `main` and `gh-pages`, then verify the live root selector, immutable V20y page, private selector, and encrypted V20y salary report.

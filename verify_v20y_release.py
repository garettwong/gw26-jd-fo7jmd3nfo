from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import subprocess
from collections import Counter
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-25-V20x"
VERSION_ID = "2026-08-25-V20y"
BUILD_ID = "v20y-hk239-city-dec-first-lesson-marker-20260825a"
TARGET_DATES = ("2026-12-16", "2026-12-17", "2026-12-18")
OLD_DATES = ("2026-11-11", "2026-11-12", "2026-11-13")
TARGET_TEXT = "城市一條龍"
OLD_TARGET_TEXT = "城巿一條龍"
SNAPSHOT_FILES = (
    "index.html",
    "events.json",
    "class_context.json",
    "payment_context.json",
    "summary.json",
    "schedule_overrides.json",
    "sw.js",
    "manifest.webmanifest",
    "favicon-32.png",
    "icon-180.png",
    "icon-192.png",
    "icon-512.png",
)
EXPECTED_V20X_HASHES = {
    "class_context.json": "51FF939DD9E11768032F9BCC0FBE33E0A53CFB7C996110E221F46A512F1DBC7D",
    "events.json": "86EA43EAFE39876366758980E37B09FD50E40EFC7DE117D3F4DC5A701FE42900",
    "favicon-32.png": "BAD3B3070ADAF8A24C2F440AB3196D64401CDE54115B9EAAAD3E3D5D7418953C",
    "icon-180.png": "C29B53D9392EA5C2800E9896178749465E69E22F20186492DEC1B80A74F14CF2",
    "icon-192.png": "39AE37C8A01B913547BC77A57B0DDFDB6145140D82FE8478BDBEBB5F5CA8FF77",
    "icon-512.png": "3A7AD8CEC1688943FF8533EF8A24BE678BDCE9C7AA4A25223477B28E74EB4B23",
    "index.html": "97A6AC6F33169A0A02A44BB497EE9DDBD7A35545981E6D8D5A4D928B8FF4D8C1",
    "manifest.webmanifest": "002997A3ADFE4D44CF298551FFA659F54F1CBDC0D450307EEA237BB357C4D3ED",
    "payment_context.json": "C7DF87B45C1573C7BC4447C7FC1D74188A76099E93DD5155DEF2F8D3CDF33686",
    "schedule_overrides.json": "5269FBE90C03BE03101DCEB771C6864F5013EB91E150AE12445E6AE4E49FFDFD",
    "summary.json": "1F9E1C40258F1D61778C7A41B724B1A2677EB7AF5022FD9A7F5784E919ACD650",
    "sw.js": "29DF695A94F0CEF039458D673649BD6888DE7AD5AD960563B37DA27EA3D9CCD2",
}
EXPECTED_V20X_SALARY_HASHES = {
    "earnings.enc.json": "EB516813BC4AB9EA3BB2D437A450A1E64D7644A63E838BEBA88DE6A2E888564D",
    "index.html": "57A5A762C10298E9B59EF1ADB2E90111B5823C17A42E8534FDAE4660B43995EF",
}
DERIVED_EVENT_KEYS = {
    "changed_in_version",
    "change_kind",
    "previous_text",
    "previous_status",
    "is_first_lesson",
}
TIME_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?\s*[-–]\s*"
    r"(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?(?!\d)"
)
LESSON_RE = re.compile(r"\bL\s*(\d+)\b", re.I)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decrypt_report(path: Path) -> dict:
    key = decode((ROOT / "private_earnings_key.txt").read_text(encoding="ascii").strip())
    payload = read_json(path)
    plaintext = AESGCM(key).decrypt(
        decode(payload["nonce"]),
        decode(payload["ciphertext"]),
        b"erb-earnings-v1",
    )
    return json.loads(plaintext.decode("utf-8"))


def event_identity(event: dict) -> tuple:
    return tuple(event.get(key) for key in ("date", "month", "row", "col", "cell"))


def strip_derived(event: dict) -> dict:
    return {key: value for key, value in event.items() if key not in DERIVED_EVENT_KEYS}


def event_intervals(text: str) -> list[tuple[int, int]]:
    intervals = []
    for match in TIME_RE.finditer(text):
        start = int(match.group(1)) * 60 + int(match.group(2) or 0)
        end = int(match.group(3)) * 60 + int(match.group(4) or 0)
        intervals.append((start, end))
    return intervals


class CardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.first_cards: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "div":
            return
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if "chip" in classes and values.get("data-first-lesson") == "1":
            self.first_cards.append(values)


def expected_row_key(row: dict) -> tuple:
    return tuple(
        row.get(key)
        for key in (
            "kind",
            "label",
            "service_period",
            "invoice_date",
            "expected_payment_date",
            "hours",
            "amount",
            "received",
        )
    )


def month_map(report_mode: dict) -> dict[str, dict]:
    return {row["month"]: row for row in report_mode["months"]}


def audit_historical_snapshots() -> dict:
    baseline = ROOT / "versions" / BASELINE_ID
    observed = {name: sha256(baseline / name) for name in EXPECTED_V20X_HASHES}
    if observed != EXPECTED_V20X_HASHES:
        raise ValueError("The immutable V20x timetable snapshot changed")
    salary_baseline = ROOT / "earnings" / "versions" / BASELINE_ID
    observed_salary = {
        name: sha256(salary_baseline / name)
        for name in EXPECTED_V20X_SALARY_HASHES
    }
    if observed_salary != EXPECTED_V20X_SALARY_HASHES:
        raise ValueError("The immutable V20x salary snapshot changed")
    diff = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "versions", "earnings/versions"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if diff:
        raise ValueError(f"A tracked historical snapshot changed: {diff}")
    return {
        "v20x_timetable_hashes": observed,
        "v20x_salary_hashes": observed_salary,
        "all_tracked_historical_snapshots_unchanged": True,
    }


def audit_snapshot_parity() -> dict:
    snapshot = ROOT / "versions" / VERSION_ID
    mismatches = [
        name for name in SNAPSHOT_FILES
        if sha256(ROOT / name) != sha256(snapshot / name)
    ]
    if mismatches:
        raise ValueError(f"Root and V20y snapshot differ: {mismatches}")
    current_salary = ROOT / "earnings" / "earnings.enc.json"
    version_salary = ROOT / "earnings" / "versions" / VERSION_ID / "earnings.enc.json"
    if current_salary.read_bytes() != version_salary.read_bytes():
        raise ValueError("Current encrypted salary payload is not the V20y payload")
    return {
        "root_matches_v20y_snapshot": True,
        "matching_files": list(SNAPSHOT_FILES),
        "root_salary_matches_v20y_encrypted_payload": True,
    }


def audit_source_preservation() -> dict:
    baseline_events = read_json(ROOT / "versions" / BASELINE_ID / "events.json")
    current_events = read_json(ROOT / "events.json")
    target_identities = {
        ("2026-11-11", "November New", 12, 11, "K12"),
        ("2026-11-11", "November New", 13, 11, "K13"),
        ("2026-11-12", "November New", 12, 14, "N12"),
        ("2026-11-12", "November New", 13, 14, "N13"),
        ("2026-11-13", "November New", 12, 17, "Q12"),
        ("2026-11-13", "November New", 13, 17, "Q13"),
    }
    baseline_map = {event_identity(event): event for event in baseline_events}
    current_map = {event_identity(event): event for event in current_events}
    removed = set(baseline_map) - set(current_map)
    added = set(current_map) - set(baseline_map)
    if removed != target_identities or added:
        raise ValueError(f"Unexpected workbook identity delta: removed={removed}, added={added}")
    for identity, event in current_map.items():
        if strip_derived(event) != strip_derived(baseline_map[identity]):
            raise ValueError(f"Non-target workbook row changed: {identity}")

    baseline_context = read_json(ROOT / "versions" / BASELINE_ID / "class_context.json")
    current_context = read_json(ROOT / "class_context.json")
    if current_context[: len(baseline_context)] != baseline_context:
        raise ValueError("An existing class-context row changed")
    additions = current_context[len(baseline_context):]
    if len(additions) != 6 or any(TARGET_TEXT not in item["text"] for item in additions):
        raise ValueError("Class-context delta is not exactly six target lessons")
    return {
        "baseline_workbook_rows": len(baseline_events),
        "current_workbook_rows": len(current_events),
        "removed_target_rows": len(removed),
        "surviving_workbook_rows_unchanged": True,
        "baseline_context_rows": len(baseline_context),
        "current_context_rows": len(current_context),
        "added_target_context_rows": len(additions),
        "existing_context_rows_unchanged": True,
    }


def audit_timetable() -> dict:
    events = read_json(ROOT / "events.json")
    context = read_json(ROOT / "class_context.json")
    target = [item for item in context if TARGET_TEXT in item.get("text", "")]
    if len(target) != 6:
        raise ValueError(f"Expected six replacement lessons, found {len(target)}")
    if any(
        (OLD_TARGET_TEXT in item.get("text", "") or TARGET_TEXT in item.get("text", ""))
        and item.get("date") in OLD_DATES
        for item in events + context
    ):
        raise ValueError("A superseded November city-course lesson remains")

    expected = [
        ("2026-12-16", "Wednesday", 1, (540, 720)),
        ("2026-12-16", "Wednesday", 2, (780, 960)),
        ("2026-12-17", "Thursday", 3, (540, 720)),
        ("2026-12-17", "Thursday", 4, (780, 960)),
        ("2026-12-18", "Friday", 5, (540, 720)),
        ("2026-12-18", "Friday", 6, (780, 960)),
    ]
    observed = []
    lesson_rows = []
    for item in sorted(target, key=lambda value: (value["date"], event_intervals(value["text"])[0])):
        lesson_match = LESSON_RE.search(item["text"])
        if not lesson_match:
            raise ValueError(f"Missing lesson number: {item}")
        primary = event_intervals(item["text"])[0]
        weekday = date.fromisoformat(item["date"]).strftime("%A")
        observed.append((item["date"], weekday, int(lesson_match.group(1)), primary))
        if (
            item.get("status") != "confirmed"
            or item.get("teacher") != "Garett"
            or item.get("layer") != "mine"
            or item.get("teaching_room") != "102"
        ):
            raise ValueError(f"Target ownership/status/room mismatch: {item}")
        lesson_rows.append({
            "lesson": int(lesson_match.group(1)),
            "date": item["date"],
            "weekday": weekday,
            "start_minutes": primary[0],
            "end_minutes": primary[1],
            "duration_minutes": primary[1] - primary[0],
            "text": item["text"],
        })
    if observed != expected:
        raise ValueError(f"Replacement timetable mismatch: {observed}")

    teaching_minutes = sum(end - start for _, _, _, (start, end) in observed)
    day_blocks: dict[str, list[tuple[int, int]]] = {}
    for event_date, _weekday, _lesson, interval in observed:
        day_blocks.setdefault(event_date, []).append(interval)
    gaps = []
    elapsed_minutes = 0
    meal_minutes = 0
    for event_date, blocks in sorted(day_blocks.items()):
        blocks.sort()
        if len(blocks) != 2 or blocks[0][1] > blocks[1][0]:
            raise ValueError(f"Unexpected overlap/block count on {event_date}: {blocks}")
        gap = blocks[1][0] - blocks[0][1]
        if gap != 60:
            raise ValueError(f"Meal gap is not 60 minutes on {event_date}: {gap}")
        gaps.append({"date": event_date, "meal_gap_minutes": gap, "travel_minutes": 0})
        elapsed_minutes += blocks[-1][1] - blocks[0][0]
        meal_minutes += gap
    independently_derived = elapsed_minutes - meal_minutes
    if teaching_minutes != 1080 or independently_derived != 1080:
        raise ValueError(
            f"Teaching-hour calculations disagree: {teaching_minutes}, {independently_derived}"
        )

    all_on_target_dates = [item for item in events + context if item.get("date") in TARGET_DATES]
    if len(all_on_target_dates) != 6 or any(TARGET_TEXT not in item.get("text", "") for item in all_on_target_dates):
        raise ValueError(f"Another timetable commitment exists on a replacement date: {all_on_target_dates}")
    l5 = next(item for item in target if "L5" in item["text"])
    l6 = next(item for item in target if "L6" in item["text"])
    if "持續評估／小組討論／專題報告" not in l5["text"]:
        raise ValueError("L5 assessment note mismatch")
    l6_intervals = event_intervals(l6["text"])
    if l6_intervals != [(780, 960), (930, 990)]:
        raise ValueError(f"L6 final-exam note mismatch: {l6_intervals}")

    payment = next(
        item for item in read_json(ROOT / "payment_context.json")
        if TARGET_TEXT in item["label"]
    )
    if payment != {
        "group": "g07",
        "label": "HK239HG · 城市一條龍",
        "course_code": "HK239HG",
        "course_name": "人工智能知識及應用證書（兼讀制）",
        "provider": "基督教勵行會",
        "full_course_start": "2026-12-16",
        "full_course_end": "2026-12-18",
        "full_lesson_entries": 6,
    }:
        raise ValueError(f"Payment context mismatch: {payment}")

    return {
        "lessons": lesson_rows,
        "lesson_count": 6,
        "teaching_minutes_block_sum": teaching_minutes,
        "teaching_hours_block_sum": teaching_minutes / 60,
        "elapsed_minutes": elapsed_minutes,
        "meal_minutes": meal_minutes,
        "teaching_minutes_elapsed_minus_meals": independently_derived,
        "daily_gaps": gaps,
        "same_centre_travel_minutes": 0,
        "other_commitments_on_target_dates": 0,
        "old_november_target_rows": 0,
        "l6_supplied_exam_interval": "15:30-16:30",
        "l6_exam_extends_beyond_nominal_lesson_minutes": 30,
        "salary_uses_explicit_nominal_lesson_block": "13:00-16:00",
        "payment_context": payment,
    }


def audit_salary() -> dict:
    baseline = decrypt_report(
        ROOT / "earnings" / "versions" / BASELINE_ID / "earnings.enc.json"
    )
    current = decrypt_report(
        ROOT / "earnings" / "versions" / VERSION_ID / "earnings.enc.json"
    )
    if current.get("version_id") != VERSION_ID:
        raise ValueError("Encrypted report is not V20y")
    modes = {}
    for mode in ("confirmed", "confirmed_and_unconfirmed"):
        before = baseline[mode]
        after = current[mode]
        if before["grand_total"] != 139750 or after["grand_total"] != 139750:
            raise ValueError(f"Unexpected {mode} grand total")
        if before["counted_events"] != 147 or after["counted_events"] != 147:
            raise ValueError(f"Unexpected {mode} counted-event total")
        before_months, after_months = month_map(before), month_map(after)
        for month in ("June", "July", "August", "September", "October"):
            if before_months[month] != after_months[month]:
                raise ValueError(f"Unrelated {mode} month changed: {month}")
        if (
            before_months["November"]["regular_hours"],
            after_months["November"]["regular_hours"],
            before_months["December"]["regular_hours"],
            after_months["December"]["regular_hours"],
        ) != (44.0, 26.0, 0.0, 18.0):
            raise ValueError(f"Unexpected {mode} month-hour transfer")
        if (
            before_months["November"]["regular_pay"],
            after_months["November"]["regular_pay"],
            before_months["December"]["regular_pay"],
            after_months["December"]["regular_pay"],
        ) != (13200.0, 7800.0, 0.0, 5400.0):
            raise ValueError(f"Unexpected {mode} month-pay transfer")

        before_schedule = before["expected_payments"]
        after_schedule = after["expected_payments"]
        before_city = next(row for row in before_schedule["rows"] if "條龍" in row["label"])
        after_city = next(row for row in after_schedule["rows"] if "條龍" in row["label"])
        expected_city = {
            "kind": "ERB",
            "label": "HK239HG · 城市一條龍",
            "course_name": "人工智能知識及應用證書（兼讀制）",
            "provider": "基督教勵行會",
            "service_period": "2026-12-16 to 2026-12-18",
            "invoice_date": "2026-12-18",
            "expected_payment_date": "2027-01-08",
            "basis": "全班最後一課後開單；按 Calvin 所述以 3 星期規劃",
            "hours": 18.0,
            "amount": 5400.0,
            "received": False,
        }
        if after_city != expected_city:
            raise ValueError(f"Unexpected {mode} target expected-payment row: {after_city}")
        before_other = [row for row in before_schedule["rows"] if row is not before_city]
        after_other = [row for row in after_schedule["rows"] if row is not after_city]
        if sorted(map(expected_row_key, before_other)) != sorted(map(expected_row_key, after_other)):
            raise ValueError(f"An unrelated {mode} expected-payment row changed")
        if before_schedule["undated"] != after_schedule["undated"]:
            raise ValueError(f"The {mode} undated payment rows changed")
        if before_schedule["dated_total"] != 132750 or after_schedule["dated_total"] != 132750:
            raise ValueError(f"Unexpected {mode} dated total")
        if date.fromisoformat(after_city["expected_payment_date"]) != date.fromisoformat(after_city["invoice_date"]) + timedelta(days=21):
            raise ValueError("Expected-payment date is not invoice date plus 21 days")

        modes[mode] = {
            "grand_total_before": before["grand_total"],
            "grand_total_after": after["grand_total"],
            "counted_entries_before": before["counted_events"],
            "counted_entries_after": after["counted_events"],
            "november_hours_before": before_months["November"]["regular_hours"],
            "november_hours_after": after_months["November"]["regular_hours"],
            "november_pay_before": before_months["November"]["regular_pay"],
            "november_pay_after": after_months["November"]["regular_pay"],
            "december_hours_before": before_months["December"]["regular_hours"],
            "december_hours_after": after_months["December"]["regular_hours"],
            "december_pay_before": before_months["December"]["regular_pay"],
            "december_pay_after": after_months["December"]["regular_pay"],
            "salary_transfer": 5400,
            "target_expected_payment": after_city,
            "dated_total_unchanged": after_schedule["dated_total"],
        }
    return {
        "encrypted_v20x_decrypted": True,
        "encrypted_v20y_decrypted": True,
        "modes": modes,
    }


def audit_selectors() -> dict:
    public = read_json(ROOT / "versions.json")
    private = read_json(ROOT / "earnings" / "versions.json")
    if public != private:
        raise ValueError("Public/private selector metadata differ")
    latest = [item for item in public if item.get("latest")]
    if len(latest) != 1 or latest[0]["id"] != VERSION_ID or public[0]["id"] != VERSION_ID:
        raise ValueError(f"V20y is not the sole first/latest release: {latest}")
    pages = {
        "root": (ROOT / "index.html").read_text(encoding="utf-8"),
        "snapshot": (ROOT / "versions" / VERSION_ID / "index.html").read_text(encoding="utf-8"),
        "master": (ROOT / "master" / "index.html").read_text(encoding="utf-8"),
        "salary": (ROOT / "earnings" / "index.html").read_text(encoding="utf-8"),
        "salary_report": (ROOT / "earnings" / "versions" / VERSION_ID / "index.html").read_text(encoding="utf-8"),
    }
    if any(VERSION_ID not in text for name, text in pages.items() if name != "salary_report"):
        raise ValueError("V20y is absent from a selector page")
    if BUILD_ID not in pages["root"] or BUILD_ID not in pages["snapshot"]:
        raise ValueError("V20y build ID is absent from a timetable page")
    if f"versions/{VERSION_ID}/earnings.enc.json" not in pages["salary"]:
        raise ValueError("Private selector does not validate against V20y")
    if VERSION_ID not in (ROOT / "master" / "sw.js").read_text(encoding="utf-8"):
        raise ValueError("Master service worker is not V20y")
    if BUILD_ID not in (ROOT / "sw.js").read_text(encoding="utf-8"):
        raise ValueError("Root service worker is not V20y")
    return {
        "public_latest": VERSION_ID,
        "private_latest": VERSION_ID,
        "metadata_equal": True,
        "sole_latest": True,
        "root_selector": True,
        "master_selector": True,
        "private_selector": True,
        "matching_salary_report": True,
    }


def audit_first_lesson_and_log() -> dict:
    current_html = (ROOT / "index.html").read_text(encoding="utf-8")
    baseline_html = (ROOT / "versions" / BASELINE_ID / "index.html").read_text(encoding="utf-8")
    parser = CardParser()
    parser.feed(current_html)
    cards = parser.first_cards
    payment_groups = {item["group"] for item in read_json(ROOT / "payment_context.json")}
    logical_counts = Counter(card.get("data-group") for card in cards)
    if set(logical_counts) != payment_groups:
        raise ValueError(
            f"First-lesson group coverage mismatch: markers={set(logical_counts)}, expected={payment_groups}"
        )
    if any(count != 2 for count in logical_counts.values()):
        raise ValueError(f"Each logical first lesson must render in grid and agenda: {logical_counts}")
    if any(card.get("data-course") != "1" for card in cards):
        raise ValueError("A non-ERB/non-Methodist card has a first-lesson marker")
    if current_html.count(">此班第一堂<") != len(cards):
        raise ValueError("First-lesson banner count differs from marked-card count")
    target_cards = [card for card in cards if TARGET_TEXT in html.unescape(card.get("data-group-label", ""))]
    if len(target_cards) != 2 or any(card.get("data-date") != "2026-12-16" for card in target_cards):
        raise ValueError(f"Target L1 marker mismatch: {target_cards}")
    summary = read_json(ROOT / "summary.json")
    if summary.get("first_lesson_markers") != len(payment_groups):
        raise ValueError("Summary first-lesson marker count mismatch")

    log_key_re = re.compile(r'data-log-key="([^"]+)"')
    old_keys = {html.unescape(value) for value in log_key_re.findall(baseline_html)}
    new_keys = {html.unescape(value) for value in log_key_re.findall(current_html)}
    removed = old_keys - new_keys
    added = new_keys - old_keys
    if len(removed) != 6 or any(OLD_TARGET_TEXT not in key for key in removed):
        raise ValueError(f"Unexpected removed lesson-log keys: {removed}")
    if len(added) != 6 or any(TARGET_TEXT not in key for key in added):
        raise ValueError(f"Unexpected added lesson-log keys: {added}")
    if not all(token in current_html for token in (
        "garett-erb-lesson-log.garettwong3.chatgpt.site",
        "schema_version:3",
        "整理並儲存",
        "其他裝置會自動更新",
    )):
        raise ValueError("V20x cross-device lesson-log flow was not preserved")
    return {
        "logical_erb_cohorts": len(payment_groups),
        "logical_first_lesson_markers": len(logical_counts),
        "rendered_markers_grid_plus_agenda": len(cards),
        "each_marker_renders_twice": True,
        "target_marker_date": "2026-12-16",
        "marker_text": "此班第一堂",
        "unchanged_lesson_log_keys_preserved": len(old_keys & new_keys),
        "removed_rescheduled_lesson_log_keys": len(removed),
        "added_rescheduled_lesson_log_keys": len(added),
        "cross_device_lesson_log_code_preserved": True,
    }


def candidate_hashes() -> dict[str, str]:
    paths = [
        ROOT / "index.html",
        ROOT / "events.json",
        ROOT / "class_context.json",
        ROOT / "payment_context.json",
        ROOT / "schedule_overrides.json",
        ROOT / "summary.json",
        ROOT / "versions.json",
        ROOT / "master" / "index.html",
        ROOT / "master" / "sw.js",
        ROOT / "earnings" / "index.html",
        ROOT / "earnings" / "versions.json",
        ROOT / "earnings" / "earnings.enc.json",
        ROOT / "earnings" / "versions" / VERSION_ID / "index.html",
        ROOT / "earnings" / "versions" / VERSION_ID / "earnings.enc.json",
    ] + [ROOT / "versions" / VERSION_ID / name for name in SNAPSHOT_FILES]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
        for path in paths
    }


def main() -> None:
    source_workbook = Path(
        r"C:\Users\garet\OneDrive\桌面\Timetable\ERB Super Timetable 04_checking 11_20260715_V07_HK239HGCW10_REDO.xlsx"
    )
    for required in (
        source_workbook,
        ROOT / "private_earnings_key.txt",
        ROOT / "versions" / BASELINE_ID,
        ROOT / "versions" / VERSION_ID,
        ROOT / "earnings" / "versions" / VERSION_ID / "earnings.enc.json",
    ):
        if not required.exists():
            raise FileNotFoundError(required)

    audit = {
        "result": "PASS",
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "version_id": VERSION_ID,
        "baseline_id": BASELINE_ID,
        "build_id": BUILD_ID,
        "source_workbook": {
            "path": str(source_workbook),
            "size": source_workbook.stat().st_size,
            "sha256": sha256(source_workbook),
            "modified_by_release": False,
        },
        "historical_preservation": audit_historical_snapshots(),
        "snapshot_parity": audit_snapshot_parity(),
        "source_preservation": audit_source_preservation(),
        "timetable": audit_timetable(),
        "salary": audit_salary(),
        "selectors": audit_selectors(),
        "first_lesson_and_lesson_log": audit_first_lesson_and_log(),
        "candidate_sha256": candidate_hashes(),
        "checks": [
            "exact six-row November removal and December replacement",
            "Wednesday/Thursday/Friday date agreement",
            "six sequential three-hour nominal lesson blocks",
            "three exact 60-minute same-centre meal gaps",
            "18 hours by block sum and elapsed-minus-meal calculation",
            "no other commitments on December 16-18",
            "room 102, Garett, confirmed, and assessment notes",
            "HKD 5,400 transfer from November to December",
            "unchanged HKD 139,750 grand totals and 147 counted entries",
            "January 8, 2027 expected payment date",
            "17 ERB cohorts with exactly one logical first-lesson marker each",
            "unchanged lesson-log keys preserved and cross-device code retained",
            "public/private V20y selector parity and encrypted report decryption",
            "root/V20y snapshot parity and immutable V20x hashes",
        ],
    }
    output = ROOT / "qa_v20y_release_audit.json"
    output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "result": audit["result"],
        "version": VERSION_ID,
        "teaching_hours": audit["timetable"]["teaching_hours_block_sum"],
        "salary_total": audit["salary"]["modes"]["confirmed"]["grand_total_after"],
        "first_lesson_markers": audit["first_lesson_and_lesson_log"]["logical_first_lesson_markers"],
        "audit": str(output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

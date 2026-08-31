from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-28-V20ac"
VERSION_ID = "2026-08-31-V20ad"
VERSION_LABEL = "2026-08-31 - V20ad"
VERSION_SUMMARY = (
    "循道衞理中心正式時間表確認灣仔 MC244EG 班號 1；六堂身份及 305 室已更正，"
    "日期、時間、導師、18 小時及薪金不變。"
)
SOURCE = Path(
    r"C:\Users\garet\Downloads\MC244EG-1_人工智能知識及應用證書_時間表V1.pdf"
)
FINAL_NAME = (
    "2026 09 11 (2026 09 11) - "
    "MC244EG_1_FINAL FINAL (CHI) - MC - 灣仔.pdf"
)
FINAL_DIR = Path(
    r"D:\Garett Super Jobs 2026\Calvin\REAL ERB\Check schedule only (Codex)"
    r"\_____05 Confirmed Schedules\00 FINAL FINAL - Calvin Confirmed"
)
FINAL_COPY = FINAL_DIR / FINAL_NAME
SOURCE_SHA256 = "5C81BE37038B687AC58CE59EFC89A0E907B3EBF8CC962351115FC0C892CE8BBC"
DATES = (
    "2026-09-11",
    "2026-10-02",
    "2026-10-09",
    "2026-10-16",
    "2026-10-23",
    "2026-10-30",
)
OLD_CLASS = "循道灣仔晚班"
NEW_CLASS = "1"
COURSE_NAME = "人工智能知識及應用證書（兼讀制）"
VENUE = "灣仔軒尼詩道22號循道衞理中心3樓305室"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def assert_root_matches_baseline() -> None:
    baseline = ROOT / "versions" / BASELINE_ID
    for name in (
        "events.json",
        "class_context.json",
        "payment_context.json",
        "summary.json",
        "schedule_overrides.json",
        "index.html",
    ):
        if (ROOT / name).read_bytes() != (baseline / name).read_bytes():
            raise ValueError(f"Root {name} does not match locked {BASELINE_ID}")


def verify_source() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    if SOURCE.stat().st_size != 305278:
        raise ValueError(f"Unexpected source size: {SOURCE.stat().st_size}")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise ValueError("Source PDF hash does not match the rendered authoritative file")
    if not FINAL_DIR.is_dir():
        raise FileNotFoundError(FINAL_DIR)
    if FINAL_COPY.exists() and sha256(FINAL_COPY) != SOURCE_SHA256:
        raise ValueError(f"Existing FINAL FINAL file has the wrong hash: {FINAL_COPY}")


def verify_target_rows(context: list[dict]) -> list[dict]:
    rows = [row for row in context if f"Class {OLD_CLASS}" in row.get("text", "")]
    if len(rows) != 6:
        raise ValueError(f"Expected six temporary-label rows, found {len(rows)}")
    if any("MC244EG" in row.get("text", "") for row in context):
        raise ValueError("MC244EG already exists in the active context")
    by_date = {row["date"]: row for row in rows}
    if set(by_date) != set(DATES):
        raise ValueError(f"Temporary-label dates differ from the PDF: {sorted(by_date)}")
    for lesson, date in enumerate(DATES, 1):
        row = by_date[date]
        text = row.get("text", "")
        required = ("HK239HG", "1845-2145", f"L{lesson}")
        if any(token not in text for token in required):
            raise ValueError(f"Unexpected temporary-label L{lesson}: {text}")
        expected_fields = {
            "status": "confirmed",
            "teacher": "Garett",
            "helper": "",
            "layer": "mine",
            "red": False,
            "teaching_room": "課室待確認",
            "room_source": "No confirmed classroom found in the reconciled source set",
        }
        for key, expected in expected_fields.items():
            if row.get(key) != expected:
                raise ValueError(
                    f"Temporary-label L{lesson} {key}={row.get(key)!r}, expected {expected!r}"
                )
    return rows


def main() -> None:
    if (ROOT / "versions" / VERSION_ID).exists():
        raise FileExistsError(f"Refusing to overwrite fixed snapshot: {VERSION_ID}")
    assert_root_matches_baseline()
    verify_source()

    context_path = ROOT / "class_context.json"
    overrides_path = ROOT / "schedule_overrides.json"
    versions_path = ROOT / "versions.json"
    context = read_json(context_path)
    overrides = read_json(overrides_path)
    versions = read_json(versions_path)

    latest = next((item.get("id") for item in versions if item.get("latest")), None)
    if latest != BASELINE_ID:
        raise ValueError(f"Expected {BASELINE_ID} as latest, found {latest!r}")
    if any(item.get("id") == VERSION_ID for item in versions):
        raise ValueError(f"Version already exists: {VERSION_ID}")
    target_rows = verify_target_rows(context)

    before_non_target = [row for row in context if row not in target_rows]
    source_reference = f"{FINAL_NAME}, lesson {{lesson}} - FINAL FINAL; SHA-256 {SOURCE_SHA256}"
    by_date = {row["date"]: row for row in target_rows}
    for lesson, date in enumerate(DATES, 1):
        row = by_date[date]
        row["text"] = (
            f"循道-灣仔 MC244EG, Class {NEW_CLASS} / {COURSE_NAME} / "
            f"{VENUE} / 1845-2145 - L{lesson}"
        )
        row["source"] = source_reference.format(lesson=lesson)
        row["teaching_room"] = "305"
        row["room_source"] = f"{FINAL_NAME}, official 上課地點 and 課室"

    after_non_target = [row for row in context if row not in target_rows]
    if after_non_target != before_non_target:
        raise ValueError("A non-target class-context row changed")

    if overrides.get("revision") != "V20y" or len(overrides.get("overrides", [])) != 124:
        raise ValueError("Unexpected V20ac override baseline")
    if any(
        "循道灣仔晚班" in json.dumps(item, ensure_ascii=False)
        or "MC244EG" in json.dumps(item, ensure_ascii=False)
        for item in overrides["overrides"]
    ):
        raise ValueError("Target class unexpectedly exists in an override row")
    overrides["revision"] = "V20ad"
    overrides["source"] = (
        "V20ac plus the authoritative MC244EG Class 1 Methodist Centre timetable PDF "
        f"archived as {FINAL_NAME}; no override row changed."
    )
    overrides["confirmation"] = (
        "MC244EG Class 1 is confirmed for Garett/黃偉漢 on 2026-09-11 and "
        "2026-10-02, 09, 16, 23 and 30, 18:45-21:45, at Methodist Centre "
        "Wanchai room 305; six official 3-hour lessons, 18 hours total."
    )

    for item in versions:
        item["latest"] = False
    versions.insert(
        0,
        {
            "id": VERSION_ID,
            "label": VERSION_LABEL,
            "summary": VERSION_SUMMARY,
            "latest": True,
        },
    )

    if not FINAL_COPY.exists():
        shutil.copy2(SOURCE, FINAL_COPY)
    if FINAL_COPY.read_bytes() != SOURCE.read_bytes():
        raise ValueError("FINAL FINAL PDF copy is not byte-identical to the source")

    write_json(context_path, context)
    write_json(overrides_path, overrides)
    write_json(versions_path, versions)

    print(
        json.dumps(
            {
                "version": VERSION_ID,
                "renamed_lessons": 6,
                "dates": list(DATES),
                "source_sha256": SOURCE_SHA256,
                "final_copy": str(FINAL_COPY),
                "final_copy_size": FINAL_COPY.stat().st_size,
                "non_target_context_rows_preserved": len(before_non_target),
                "override_rows_preserved": len(overrides["overrides"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

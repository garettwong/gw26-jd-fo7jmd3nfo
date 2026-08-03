from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-03-V20f"
VERSION_ID = "2026-08-03-V20g"
VERSION_LABEL = "2026-08-03 - V20g"
BUILD_ID = "v20g-wanchai-night-class-lesson-log-20260803a"
VERSION_SUMMARY = "灣仔循道六堂週五晚班已確認；新增私人跨裝置課後記錄。"
DATES = (
    "2026-09-11",
    "2026-10-02",
    "2026-10-09",
    "2026-10-16",
    "2026-10-23",
    "2026-10-30",
)
LABEL = "HK239HG · 循道灣仔晚班"
SITE_FILES = (
    "class_context.json",
    "events.json",
    "favicon-32.png",
    "icon-180.png",
    "icon-192.png",
    "icon-512.png",
    "index.html",
    "manifest.webmanifest",
    "payment_context.json",
    "schedule_overrides.json",
    "summary.json",
    "sw.js",
)
EARNINGS_AAD = b"erb-earnings-v1"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decrypt_earnings(version_id: str) -> dict:
    key = decode((ROOT / "private_earnings_key.txt").read_text(encoding="ascii").strip())
    payload = read_json(ROOT / "earnings" / "versions" / version_id / "earnings.enc.json")
    plaintext = AESGCM(key).decrypt(
        decode(payload["nonce"]), decode(payload["ciphertext"]), EARNINGS_AAD
    )
    return json.loads(plaintext.decode("utf-8"))


def update_versions() -> None:
    versions = [item for item in read_json(ROOT / "versions.json") if item["id"] != VERSION_ID]
    for item in versions:
        item["latest"] = False
    versions.insert(0, {
        "id": VERSION_ID,
        "label": VERSION_LABEL,
        "summary": VERSION_SUMMARY,
        "latest": True,
    })
    write_json(ROOT / "versions.json", versions)


def snapshot() -> None:
    destination = ROOT / "versions" / VERSION_ID
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite fixed snapshot: {destination}")
    destination.mkdir(parents=True)
    for name in SITE_FILES:
        source = ROOT / name
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, destination / name)


def main() -> None:
    baseline = ROOT / "versions" / BASELINE_ID
    destination = ROOT / "versions" / VERSION_ID
    if not baseline.exists():
        raise FileNotFoundError(baseline)
    if destination.exists():
        raise FileExistsError(destination)

    baseline_hashes = {name: sha256(baseline / name) for name in SITE_FILES}
    for name in ("class_context.json", "schedule_overrides.json", "payment_context.json"):
        shutil.copy2(baseline / name, ROOT / name)

    context = read_json(ROOT / "class_context.json")
    for lesson, date in enumerate(DATES, 1):
        context.append({
            "date": date,
            "status": "confirmed",
            "text": (
                "循道-灣仔 HK239HG, Class 循道灣仔晚班 / "
                "人工智能知識及應用證書 (兼讀制) / "
                "循道衛理中心 - 香港灣仔軒尼詩道22號 / "
                f"1845-2145 - L{lesson}"
            ),
            "teacher": "Garett",
            "helper": "",
            "layer": "mine",
            "red": False,
            "source": (
                "Calvin WhatsApp confirmation 2026-08-03: six Friday evening lessons; "
                "school replaced 2026-09-18 with 2026-10-30; formal class label pending."
            ),
        })
    write_json(ROOT / "class_context.json", context)

    payments = read_json(ROOT / "payment_context.json")
    if any(item.get("label") == LABEL for item in payments):
        raise ValueError(f"Payment context already contains {LABEL}")
    payments.append({
        "group": "g26",
        "label": LABEL,
        "course_code": "HK239HG",
        "course_name": "人工智能知識及應用證書（兼讀制）",
        "provider": "循道衛理中心",
        "full_course_start": DATES[0],
        "full_course_end": DATES[-1],
        "full_lesson_entries": 6,
    })
    write_json(ROOT / "payment_context.json", payments)

    overrides = read_json(ROOT / "schedule_overrides.json")
    overrides["revision"] = "V20g"
    overrides["source"] = "V20f plus the confirmed HK239HG Methodist Wanchai Friday-night class."
    overrides["confirmation"] = (
        "Calvin confirmed on 2026-08-03 that the class runs on 2026-09-11, "
        "2026-10-02, 09, 16, 23 and 30 from 18:45 to 21:45."
    )
    write_json(ROOT / "schedule_overrides.json", overrides)

    update_versions()
    subprocess.run([sys.executable, "generate_site.py"], cwd=ROOT, check=True)

    current_context = read_json(ROOT / "class_context.json")
    added = [item for item in current_context if "Class 循道灣仔晚班" in item.get("text", "")]
    if len(added) != 6:
        raise ValueError(f"Expected six Wanchai lessons, found {len(added)}")
    if {item["date"] for item in added} != set(DATES):
        raise ValueError("Wanchai lesson dates do not match the confirmation")
    if any(item["status"] != "confirmed" or item["teacher"] != "Garett" for item in added):
        raise ValueError("A Wanchai lesson is not confirmed for Garett")
    if any("1845-2145" not in item["text"] for item in added):
        raise ValueError("A Wanchai lesson has the wrong time")

    summary = read_json(ROOT / "summary.json")
    expected_summary = {
        "override_revision": "V20g",
        "events": 185,
        "context_events": 155,
        "display_events": 340,
        "changed_in_version": 6,
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            raise ValueError(f"{key}: {summary.get(key)!r}, expected {value!r}")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    required_markers = (
        BUILD_ID,
        LABEL,
        "lessonLogModal",
        "lesson-log-open",
        "erb-lesson-log",
    )
    for marker in required_markers:
        if marker not in html:
            raise ValueError(f"Missing lesson-log/site marker: {marker}")

    snapshot()
    subprocess.run([sys.executable, "generate_earnings.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "generate_master.py"], cwd=ROOT, check=True)

    baseline_salary = decrypt_earnings(BASELINE_ID)
    salary = decrypt_earnings(VERSION_ID)
    for mode in ("confirmed", "confirmed_and_unconfirmed"):
        before = baseline_salary[mode]
        after = salary[mode]
        if after["grand_total"] - before["grand_total"] != 5400.0:
            raise ValueError(f"{mode} salary delta is not HK$5,400")
        before_months = {item["month"]: item for item in before["months"]}
        after_months = {item["month"]: item for item in after["months"]}
        if after_months["September"]["regular_hours"] - before_months["September"]["regular_hours"] != 3.0:
            raise ValueError(f"{mode} September delta is not three hours")
        if after_months["October"]["regular_hours"] - before_months["October"]["regular_hours"] != 15.0:
            raise ValueError(f"{mode} October delta is not fifteen hours")

    after_hashes = {name: sha256(baseline / name) for name in SITE_FILES}
    if after_hashes != baseline_hashes:
        raise ValueError("V20f fixed snapshot was modified")

    print(json.dumps({
        "version": VERSION_ID,
        "build": BUILD_ID,
        "confirmed_wanchai_lessons": len(added),
        "dates": list(DATES),
        "salary_confirmed": salary["confirmed"]["grand_total"],
        "salary_all": salary["confirmed_and_unconfirmed"]["grand_total"],
        "summary": expected_summary,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

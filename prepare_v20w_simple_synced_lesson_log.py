from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-22-V20v"
VERSION_ID = "2026-08-25-V20w"
VERSION_LABEL = "2026-08-25 - V20w"
BUILD_ID = "v20w-simple-synced-lesson-log-20260825a"
VERSION_SUMMARY = (
    "課後教學記錄簡化為單一大型輸入欄；按一次即可整理內容、儲存及同步至其他已連接裝置。"
    "課堂及薪金資料不變。"
)
SITE_FILES = (
    "class_context.json", "events.json", "favicon-32.png", "icon-180.png",
    "icon-192.png", "icon-512.png", "index.html", "manifest.webmanifest",
    "payment_context.json", "schedule_overrides.json", "summary.json", "sw.js",
)
AAD = b"erb-earnings-v1"
COMPARISON_FIELDS = {"changed_in_version", "change_kind", "previous_text", "previous_status"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decrypt_report(path: Path) -> dict:
    key = decode((ROOT / "private_earnings_key.txt").read_text(encoding="ascii").strip())
    payload = read_json(path)
    plaintext = AESGCM(key).decrypt(decode(payload["nonce"]), decode(payload["ciphertext"]), AAD)
    return json.loads(plaintext.decode("utf-8"))


def normalize_salary(report: dict) -> dict:
    copy = json.loads(json.dumps(report))
    for key in ("version_id", "version", "generated", "generated_at"):
        copy.pop(key, None)
    return copy


def stable_events(events: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in event.items() if key not in COMPARISON_FIELDS}
        for event in events
    ]


def run_script(name: str) -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, name], cwd=ROOT, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"{name} failed ({result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def patch_generator() -> None:
    path = ROOT / "generate_site.py"
    text = path.read_text(encoding="utf-8")
    replacements = {
        r'BUILD_ID = "[^"]+"': f'BUILD_ID = "{BUILD_ID}"',
        r'COMPARE_BASELINE = OUTDIR / "versions" / "[^"]+"':
            f'COMPARE_BASELINE = OUTDIR / "versions" / "{BASELINE_ID}"',
        r'COMPARE_LABEL = "[^"]+"': 'COMPARE_LABEL = "V20w"',
        r'COMPARE_BASELINE_LABEL = "[^"]+"': 'COMPARE_BASELINE_LABEL = "V20v"',
        r"EXPECTED_COMPARISON_CHANGES = \d+": "EXPECTED_COMPARISON_CHANGES = 0",
    }
    for pattern, replacement in replacements.items():
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise ValueError(f"Expected one generator marker for {pattern!r}")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    baseline = ROOT / "versions" / BASELINE_ID
    destination = ROOT / "versions" / VERSION_ID
    salary_destination = ROOT / "earnings" / "versions" / VERSION_ID
    if not baseline.exists():
        raise FileNotFoundError(baseline)
    if destination.exists() or salary_destination.exists():
        raise FileExistsError(f"Refusing to overwrite {VERSION_ID}")

    baseline_hashes = {name: sha256(baseline / name) for name in SITE_FILES}
    baseline_salary = decrypt_report(
        ROOT / "earnings" / "versions" / BASELINE_ID / "earnings.enc.json"
    )
    versions_before = (ROOT / "versions.json").read_bytes()
    salary_versions_before = (ROOT / "earnings" / "versions.json").read_bytes()
    generator_before = (ROOT / "generate_site.py").read_bytes()
    root_backups = {
        name: (ROOT / name).read_bytes()
        for name in ("class_context.json", "schedule_overrides.json", "payment_context.json")
    }

    try:
        for name in ("class_context.json", "schedule_overrides.json", "payment_context.json"):
            shutil.copy2(baseline / name, ROOT / name)

        overrides = read_json(ROOT / "schedule_overrides.json")
        overrides["revision"] = "V20w"
        overrides["source"] = "V20v plus the simplified synced lesson-record interface on 2026-08-25."
        overrides["confirmation"] = (
            "Interface-only release. Dates, times, teachers, rooms, statuses, salary ownership "
            "and payment records are unchanged from V20v."
        )
        write_json(ROOT / "schedule_overrides.json", overrides)

        versions = read_json(ROOT / "versions.json")
        latest = [item for item in versions if item.get("latest")]
        if len(latest) != 1 or latest[0].get("id") != BASELINE_ID:
            raise ValueError(f"Unexpected latest baseline: {latest}")
        if any(item.get("id") == VERSION_ID for item in versions):
            raise FileExistsError(VERSION_ID)
        for item in versions:
            item["latest"] = False
        versions.insert(0, {
            "id": VERSION_ID,
            "label": VERSION_LABEL,
            "summary": VERSION_SUMMARY,
            "latest": True,
        })
        write_json(ROOT / "versions.json", versions)

        patch_generator()
        run_script("generate_site.py")

        if stable_events(read_json(ROOT / "events.json")) != stable_events(read_json(baseline / "events.json")):
            raise ValueError("V20w unexpectedly changed timetable events")
        for name in ("class_context.json", "payment_context.json"):
            if (ROOT / name).read_bytes() != (baseline / name).read_bytes():
                raise ValueError(f"V20w unexpectedly changed {name}")
        summary = read_json(ROOT / "summary.json")
        baseline_summary = read_json(baseline / "summary.json")
        for key in ("events", "context_events", "display_events", "counts", "layers", "categories"):
            if summary.get(key) != baseline_summary.get(key):
                raise ValueError(f"V20w changed schedule field {key}")
        if summary.get("changed_in_version") != 0 or summary.get("comparison_label") != "V20w":
            raise ValueError("V20w comparison metadata is incorrect")

        html = (ROOT / "index.html").read_text(encoding="utf-8")
        required = (
            BUILD_ID, "課後教學記錄", "今堂教了甚麼", "整理並儲存", "同步設定",
            "combined_text", "polishTeachingText", "正在讀取其他裝置的最新記錄",
            "min-height:300px", "min-height:48vh",
        )
        missing = [item for item in required if item not in html]
        if missing:
            raise ValueError(f"Missing V20w interface fragments: {missing}")
        forbidden = (
            "lessonLogProgress", "lessonLogFollowUp", "lessonLogRemarks",
            'id="lessonLogSync"', "手機／電腦同步設定",
        )
        present = [item for item in forbidden if item in html]
        if present:
            raise ValueError(f"Old multi-field interface remains: {present}")

        destination.mkdir(parents=True)
        for name in SITE_FILES:
            shutil.copy2(ROOT / name, destination / name)

        run_script("generate_earnings.py")
        run_script("generate_master.py")
        if not salary_destination.exists():
            raise FileNotFoundError(salary_destination)

        public_versions = read_json(ROOT / "versions.json")
        private_versions = read_json(ROOT / "earnings" / "versions.json")
        if public_versions != private_versions:
            raise ValueError("Timetable and salary selectors are not in lockstep")
        if public_versions[0].get("id") != VERSION_ID or not public_versions[0].get("latest"):
            raise ValueError("V20w is not first/latest")
        current_salary = decrypt_report(salary_destination / "earnings.enc.json")
        if normalize_salary(current_salary) != normalize_salary(baseline_salary):
            raise ValueError("V20w changed salary data")
        if current_salary.get("version_id") != VERSION_ID:
            raise ValueError("Encrypted salary report has the wrong version ID")

        for name, digest in baseline_hashes.items():
            if sha256(baseline / name) != digest:
                raise ValueError(f"Historical V20v snapshot changed: {name}")

        audit = {
            "result": "PASS",
            "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "version_id": VERSION_ID,
            "build_id": BUILD_ID,
            "baseline": BASELINE_ID,
            "schedule_unchanged": True,
            "salary_unchanged": True,
            "single_large_field": True,
            "legacy_records_preserved": True,
            "cross_device_sync": True,
        }
        write_json(ROOT / "qa_v20w_release_audit.json", audit)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        if salary_destination.exists():
            shutil.rmtree(salary_destination)
        (ROOT / "versions.json").write_bytes(versions_before)
        (ROOT / "earnings" / "versions.json").write_bytes(salary_versions_before)
        (ROOT / "generate_site.py").write_bytes(generator_before)
        for name, payload in root_backups.items():
            (ROOT / name).write_bytes(payload)
        raise


if __name__ == "__main__":
    main()

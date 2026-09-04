from __future__ import annotations

import base64
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
BASELINE_ID = "2026-09-01-V20af"
VERSION_ID = "2026-09-04-V20ag"
VERSION_LABEL = "2026-09-04 - V20ag"
BUILD_ID = "v20ag-upcoming-column-order-place-readability-20260904a"
VERSION_SUMMARY = (
    "改善 Upcoming classes 閱讀次序：桌面先讀完整左欄再讀右欄；中心及地點／課室分開放大。"
    "Next 5／10／15、課堂及薪酬資料不變。"
)
SITE_FILES = (
    "class_context.json", "events.json", "favicon-32.png", "icon-180.png",
    "icon-192.png", "icon-512.png", "index.html", "manifest.webmanifest",
    "payment_context.json", "schedule_overrides.json", "summary.json", "sw.js",
)
DATA_FILES = ("events.json", "class_context.json", "payment_context.json", "schedule_overrides.json")
AAD = b"erb-earnings-v1"
EXPECTED_DATES = [
    "2026-09-11", "2026-09-16", "2026-09-21", "2026-09-23", "2026-10-03",
    "2026-10-03", "2026-11-11", "2026-11-23", "2026-12-16",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_script(name: str) -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, name], cwd=ROOT, env=env, text=True,
        encoding="utf-8", errors="replace", capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"{name} failed\n{result.stdout}\n{result.stderr}")


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def decrypt_report(path: Path) -> dict:
    key = decode((ROOT / "private_earnings_key.txt").read_text(encoding="ascii").strip())
    payload = read_json(path)
    clear = AESGCM(key).decrypt(decode(payload["nonce"]), decode(payload["ciphertext"]), AAD)
    return json.loads(clear.decode("utf-8"))


def normalized_report(report: dict) -> dict:
    result = json.loads(json.dumps(report))
    for key in ("version_id", "version", "generated", "generated_at"):
        result.pop(key, None)
    return result


def main() -> None:
    baseline = ROOT / "versions" / BASELINE_ID
    destination = ROOT / "versions" / VERSION_ID
    salary_destination = ROOT / "earnings" / "versions" / VERSION_ID
    if destination.exists() or salary_destination.exists():
        raise FileExistsError(f"Refusing to overwrite {VERSION_ID}")
    for path in (baseline, ROOT / "private_earnings_key.txt"):
        if not path.exists():
            raise FileNotFoundError(path)

    protected = [
        ROOT / "versions.json", ROOT / "earnings" / "versions.json",
        ROOT / "earnings" / "index.html", ROOT / "earnings" / "earnings.enc.json",
        ROOT / "master" / "index.html", ROOT / "master" / "sw.js",
        *(ROOT / name for name in SITE_FILES),
    ]
    backups = {path: path.read_bytes() for path in protected if path.exists()}
    historical_salary = {
        path: path.read_bytes()
        for path in (ROOT / "earnings" / "versions").glob("*/earnings.enc.json")
    }

    try:
        versions = read_json(ROOT / "versions.json")
        latest = [item for item in versions if item.get("latest")]
        if len(latest) != 1 or latest[0]["id"] != BASELINE_ID:
            raise ValueError(f"Unexpected public baseline: {latest}")
        for item in versions:
            item["latest"] = False
        versions.insert(0, {
            "id": VERSION_ID, "label": VERSION_LABEL,
            "summary": VERSION_SUMMARY, "latest": True,
        })
        write_json(ROOT / "versions.json", versions)

        run_script("generate_site.py")
        for name in DATA_FILES:
            if (ROOT / name).read_bytes() != (baseline / name).read_bytes():
                raise ValueError(f"Display-only release changed {name}")
        summary = read_json(ROOT / "summary.json")
        if summary.get("changed_in_version") != 0 or summary.get("comparison_label") != "V20ag":
            raise ValueError("Comparison metadata is not a zero-record V20ag delta")

        page = (ROOT / "index.html").read_text(encoding="utf-8")
        cards = re.findall(r'<article class="next-course-card"[^>]*>', page)
        dates = [re.search(r'data-first-date="([^"]+)"', card).group(1) for card in cards]
        if dates != EXPECTED_DATES:
            raise ValueError(f"Unexpected upcoming order: {dates}")
        if len(re.findall(r'class="next-course-fact place centre"', page)) != 9:
            raise ValueError("Centre fields are not separated for every card")
        if len(re.findall(r'class="next-course-fact place location"', page)) != 9:
            raise ValueError("Location/room fields are not separated for every card")
        for marker in ("Next 5", "Next 10", "Next 15", "grid-auto-flow:column", BUILD_ID):
            if marker not in page:
                raise ValueError(f"Missing UI marker: {marker}")
        hk281 = next(card for card in cards if 'data-first-lesson="Lesson 52"' in card)
        if 'data-first-date="2026-10-03"' not in hk281 or 'data-class-first-date="2026-08-31"' not in hk281:
            raise ValueError("HK281DS CW7 Garett-first semantics changed")

        destination.mkdir(parents=True)
        for name in SITE_FILES:
            shutil.copy2(ROOT / name, destination / name)

        run_script("generate_earnings.py")
        run_script("generate_master.py")
        if not salary_destination.exists():
            raise FileNotFoundError(salary_destination)
        for path, content in historical_salary.items():
            if path.read_bytes() != content:
                raise ValueError(f"Historical salary payload changed: {path}")

        public_versions = read_json(ROOT / "versions.json")
        private_versions = read_json(ROOT / "earnings" / "versions.json")
        if public_versions != private_versions:
            raise ValueError("Public/private selectors are not in lockstep")
        if public_versions[0]["id"] != VERSION_ID or not public_versions[0].get("latest"):
            raise ValueError("V20ag is not the sole latest release")
        if sum(bool(item.get("latest")) for item in public_versions) != 1:
            raise ValueError("Selector has multiple latest entries")

        baseline_salary = decrypt_report(ROOT / "earnings" / "versions" / BASELINE_ID / "earnings.enc.json")
        current_salary = decrypt_report(salary_destination / "earnings.enc.json")
        if normalized_report(current_salary) != normalized_report(baseline_salary):
            raise ValueError("Salary rows or amounts changed")
        if current_salary.get("version_id") != VERSION_ID:
            raise ValueError("Encrypted salary has the wrong version ID")
        if (ROOT / "earnings" / "earnings.enc.json").read_bytes() != (salary_destination / "earnings.enc.json").read_bytes():
            raise ValueError("Root salary payload is not the V20ag snapshot")

        audit = {
            "result": "PASS",
            "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
            "version_id": VERSION_ID,
            "build_id": BUILD_ID,
            "baseline_id": BASELINE_ID,
            "upcoming_dates": dates,
            "upcoming_count": len(cards),
            "lesson_data_unchanged": True,
            "salary_data_unchanged": True,
            "historical_salary_payloads_unchanged": True,
            "public_private_version_parity": True,
        }
        write_json(ROOT / "qa_v20ag_release_audit.json", audit)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    except Exception:
        for path, content in backups.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for path, content in historical_salary.items():
            path.write_bytes(content)
        shutil.rmtree(destination, ignore_errors=True)
        shutil.rmtree(salary_destination, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


sys.stdout.reconfigure(encoding="utf-8")


SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
PDFTOPPM = Path(
    r"C:\Users\garet\.cache\codex-runtimes\codex-primary-runtime\dependencies"
    r"\native\poppler\Library\bin\pdftoppm.exe"
)


def run_with_timeout(command: list[str], timeout: int) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        raise RuntimeError(f"Command timed out after {timeout}s: {command[0]}")
    if process.returncode:
        raise RuntimeError(
            f"Command failed ({process.returncode}): {command[0]}\n{stdout}\n{stderr}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    source = args.input.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not SOFFICE.is_file():
        raise FileNotFoundError(SOFFICE)
    if not PDFTOPPM.is_file():
        raise FileNotFoundError(PDFTOPPM)

    with tempfile.TemporaryDirectory(prefix="codex_lo_profile_") as profile_tmp:
        with tempfile.TemporaryDirectory(prefix="codex_lo_convert_") as convert_tmp:
            profile_uri = Path(profile_tmp).resolve().as_uri()
            convert_dir = Path(convert_tmp).resolve()
            run_with_timeout(
                [
                    str(SOFFICE),
                    f"-env:UserInstallation={profile_uri}",
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(convert_dir),
                    str(source),
                ],
                timeout=120,
            )
            converted = convert_dir / f"{source.stem}.pdf"
            if not converted.is_file() or converted.stat().st_size == 0:
                raise RuntimeError("LibreOffice did not create a non-empty PDF")
            pdf_path = output_dir / converted.name
            shutil.copy2(converted, pdf_path)

    page_prefix = output_dir / "page"
    run_with_timeout(
        [str(PDFTOPPM), "-png", "-r", "160", str(pdf_path), str(page_prefix)],
        timeout=120,
    )
    pages = sorted(output_dir.glob("page-*.png"))
    if not pages:
        raise RuntimeError("No page PNG was produced")
    print(pdf_path)
    for page in pages:
        print(page)


if __name__ == "__main__":
    main()

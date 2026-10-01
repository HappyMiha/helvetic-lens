"""Bounded local page OCR. No network or generative reconstruction of missing text."""
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

MAX_OCR_PAGES = 4


def pdf_pages(body, numbers):
    if not shutil.which("tesseract") or not shutil.which("pdftoppm"):
        return [], ["Local OCR is unavailable; scanned pages were not read."]
    sections, warnings = [], []
    with TemporaryDirectory(prefix="lens-ocr-") as folder:
        path = Path(folder)
        (path / "original.pdf").write_bytes(body)
        for number in numbers[:MAX_OCR_PAGES]:
            try:
                subprocess.run(["pdftoppm", "-f", str(number), "-l", str(number), "-singlefile",
                    "-scale-to", "2200", "-png", str(path / "original.pdf"), str(path / "page")],
                    check=True, timeout=8, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["tesseract", str(path / "page.png"), str(path / "text"),
                    "-l", "eng+deu+fra+ita", "--psm", "3"],
                    env={**os.environ, "OMP_THREAD_LIMIT": "1"}, check=True, timeout=8,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                text = (path / "text.txt").read_text(encoding="utf-8")[:24000]
                if text.strip():
                    sections.append((f"page-{number}-ocr", text))
                else:
                    warnings.append(f"Page {number}: OCR found no readable text.")
            except (OSError, subprocess.SubprocessError):
                warnings.append(f"Page {number}: OCR could not finish within its limits.")
    if len(numbers) > MAX_OCR_PAGES:
        warnings.append("Only the first four scanned pages were processed by OCR.")
    return sections, warnings

"""Canonical md->pdf generator using headless Chromium for layout.

Usage: python pdfgen2.py "<source.md>" "<output.pdf>" "<footer text>"

Why Chromium: PyMuPDF's Story engine does not repeat <thead> across page
breaks and misplaces filled backgrounds near breaks. A browser print engine
repeats table headers on every page, paginates correctly, renders real color
emoji, and honours background fills. We render the body with Chromium, then
stamp the footer + page numbers with PyMuPDF (vector, lossless).
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import fitz
import markdown

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# Bottom margin is generous so our stamped footer never collides with content.
CSS = """
@page { size: A4; margin: 14mm 13mm 17mm 13mm; }

* { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 10.5pt;
  line-height: 1.45;
  color: #1f2937;
  margin: 0;
}

h1, h2, h3, h4 { color: #111827; margin: 16pt 0 7pt; break-after: avoid; }
h1 { font-size: 20pt; border-bottom: 1.2px solid #cbd5e1; padding-bottom: 7pt; margin-top: 0; }
h2 { font-size: 14pt; background: #f3f4f6; padding: 6pt 9pt; border: 0.8px solid #e5e7eb; border-radius: 3px; }
h3 { font-size: 12pt; }

p { margin: 5pt 0; orphans: 3; widows: 3; }

blockquote {
  margin: 9pt 0; padding: 7pt 11pt;
  background: #f9fafb; border-left: 3px solid #9ca3af; color: #374151;
  break-inside: avoid;
}

ul, ol { margin: 5pt 0 8pt; padding-left: 18pt; }
li { margin-bottom: 3pt; }

code { font-family: Consolas, "Courier New", monospace; font-size: 9.3pt;
       background: #f3f4f6; color: #b91c1c; padding: 0 2px; border-radius: 2px; }
pre  { background: #f6f8fa; border: 1px solid #d1d5db; border-radius: 3px;
       padding: 9pt; margin: 9pt 0; break-inside: avoid; overflow: hidden; }
pre code { background: transparent; color: #111827; padding: 0; }

table { width: 100%; border-collapse: collapse; margin: 9pt 0 12pt; font-size: 9.4pt; }
th, td { border: 1px solid #cbd5e1; padding: 6pt 7pt; vertical-align: top; text-align: left; }
thead { display: table-header-group; }      /* browsers repeat this on every page */
th { background: #e5e7eb; color: #111827; font-weight: bold; }
tr { break-inside: avoid; }

hr { border: none; border-top: 1px solid #d1d5db; margin: 14pt 0; }
"""

# --- footer geometry (must match @page bottom margin above) -----------------
PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
LEFT = RIGHT = 13 * 72 / 25.4  # 13mm in points


def find_chrome() -> str:
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    raise RuntimeError("No Chrome/Edge found for PDF rendering.")


def md_to_html(md_text: str) -> str:
    body = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code", "sane_lists", "toc"],
        output_format="html5",
        tab_length=2,  # source files nest sub-bullets with 2 spaces
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def chrome_print(chrome: str, html_path: Path, pdf_path: Path) -> None:
    url = html_path.resolve().as_uri()
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=15000",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path}",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # Chrome sometimes needs a beat to flush the file handle.
    for _ in range(20):
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            break
        time.sleep(0.2)
    if not (pdf_path.exists() and pdf_path.stat().st_size > 0):
        raise RuntimeError(f"Chrome did not produce a PDF.\nSTDERR:\n{res.stderr}")


def stamp_footer(pdf_path: Path, footer_text: str) -> None:
    doc = fitz.open(pdf_path)
    for index, page in enumerate(doc, start=1):
        w = page.rect.width
        h = page.rect.height
        y_line = h - (17 * 72 / 25.4) + 10   # inside the bottom margin band
        page.draw_line(fitz.Point(LEFT, y_line), fitz.Point(w - RIGHT, y_line),
                       color=(0.78, 0.82, 0.88), width=0.6)
        page.insert_textbox(
            fitz.Rect(LEFT, y_line + 3, w - RIGHT, h - 8),
            f"{footer_text}    Page {index}",
            fontsize=8.5, fontname="helv", color=(0.35, 0.41, 0.5),
            align=fitz.TEXT_ALIGN_CENTER,
        )
    tmp = pdf_path.with_name(pdf_path.stem + ".stamped.pdf")
    doc.save(tmp)
    doc.close()
    pdf_path.unlink()
    tmp.rename(pdf_path)


def build(md_path: Path, pdf_path: Path, footer_text: str) -> None:
    html = md_to_html(md_path.read_text(encoding="utf-8"))
    html_path = pdf_path.with_suffix(".src.html")
    html_path.write_text(html, encoding="utf-8")
    try:
        chrome_print(find_chrome(), html_path, pdf_path)
        stamp_footer(pdf_path, footer_text)
    finally:
        if html_path.exists():
            html_path.unlink()

BASE_DIR = Path(__file__).resolve().parent
SOURCE_MD = BASE_DIR / "assignment.md"
OUTPUT_PDF = BASE_DIR / "assignment.pdf"
FOOTER_TEXT = "Phase 7 Assignment 7B - Backend API Projects"


if __name__ == "__main__":
    build(SOURCE_MD, OUTPUT_PDF, FOOTER_TEXT)
    print(f"Created: {OUTPUT_PDF}  ({fitz.open(OUTPUT_PDF).page_count} pages)")

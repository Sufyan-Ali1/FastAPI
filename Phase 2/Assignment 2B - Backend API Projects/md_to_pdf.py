from pathlib import Path

import fitz
import markdown


BASE_DIR = Path(__file__).resolve().parent
SOURCE_MD = BASE_DIR / "assignment.md"
OUTPUT_PDF = BASE_DIR / "assignment.pdf"


CSS = """
body {
  font-family: Helvetica, Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.42;
  color: #1f2937;
  margin: 0;
}

h1, h2, h3, h4 {
  color: #111827;
  margin-top: 16pt;
  margin-bottom: 7pt;
  page-break-after: avoid;
  break-after: avoid-page;
}

h1 {
  font-size: 19pt;
  border-bottom: 1.2px solid #cbd5e1;
  padding-bottom: 7pt;
  margin-top: 0;
}

h2 {
  font-size: 14pt;
  background: #f3f4f6;
  padding: 6pt 8pt;
  border: 0.8px solid #e5e7eb;
}

h3 {
  font-size: 12pt;
}

p {
  margin: 5pt 0;
  orphans: 3;
  widows: 3;
}

blockquote {
  margin: 9pt 0;
  padding: 8pt 10pt;
  background: #f9fafb;
  border-left: 3px solid #9ca3af;
  color: #374151;
  page-break-inside: avoid;
}

ul, ol {
  margin-top: 5pt;
  margin-bottom: 8pt;
  padding-left: 18pt;
}

li {
  margin-bottom: 3pt;
}

code {
  font-family: Courier, monospace;
  font-size: 9.5pt;
  background: #f3f4f6;
  color: #111827;
}

pre {
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  padding: 8pt;
  margin: 9pt 0;
  page-break-inside: avoid;
}

pre code {
  background: transparent;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 9pt 0 12pt 0;
  font-size: 9.5pt;
  page-break-inside: auto;
}

th, td {
  border: 1px solid #d1d5db;
  padding: 6pt 7pt;
  vertical-align: top;
}

th {
  background: #e5e7eb;
  color: #111827;
  font-weight: bold;
}

hr {
  border: none;
  border-top: 1px solid #d1d5db;
  margin: 14pt 0;
}

p + ul,
p + ol {
  margin-top: 3pt;
}

ul + p,
ol + p,
table + p,
pre + p {
  margin-top: 7pt;
}

thead {
  display: table-header-group;
}

tr {
  page-break-inside: avoid;
}
"""


PAGE_WIDTH, PAGE_HEIGHT = fitz.paper_size("a4")
PAGE_RECT = fitz.Rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT)
LEFT_MARGIN = 42
RIGHT_MARGIN = 42
TOP_MARGIN = 42
BOTTOM_MARGIN = 46
FOOTER_HEIGHT = 22
CONTENT_RECT = fitz.Rect(
    LEFT_MARGIN,
    TOP_MARGIN,
    PAGE_WIDTH - RIGHT_MARGIN,
    PAGE_HEIGHT - BOTTOM_MARGIN - FOOTER_HEIGHT,
)
FOOTER_TEXT = "Phase 2 Assignment 2B - Backend API Projects"


def markdown_to_html(md_text: str) -> str:
    html_body = markdown.markdown(
        md_text,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "sane_lists",
            "toc",
        ],
        output_format="html5",
    )
    return f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"


def build_pdf(html: str, output_path: Path) -> None:
    archive = fitz.Archive()
    story = fitz.Story(html=html, archive=archive)
    temp_story_output = output_path.with_name(f"{output_path.stem}.story.pdf")
    if temp_story_output.exists():
        temp_story_output.unlink()

    writer = fitz.DocumentWriter(str(temp_story_output))
    more = True
    while more:
        device = writer.begin_page(PAGE_RECT)
        more, _ = story.place(CONTENT_RECT)
        story.draw(device)
        writer.end_page()
    writer.close()

    add_page_furniture(temp_story_output, output_path)
    if temp_story_output.exists():
        try:
            temp_story_output.unlink()
        except PermissionError:
            pass


def add_page_furniture(source_path: Path, output_path: Path) -> None:
    doc = fitz.open(source_path)

    for index, page in enumerate(doc, start=1):
        footer_y = PAGE_RECT.y1 - BOTTOM_MARGIN - 6
        page.draw_line(
            fitz.Point(LEFT_MARGIN, footer_y),
            fitz.Point(PAGE_RECT.x1 - RIGHT_MARGIN, footer_y),
            color=(0.78, 0.82, 0.88),
            width=0.6,
        )
        page.insert_textbox(
            fitz.Rect(
                LEFT_MARGIN,
                PAGE_RECT.y1 - BOTTOM_MARGIN + 2,
                PAGE_RECT.x1 - RIGHT_MARGIN,
                PAGE_RECT.y1 - 10,
            ),
            f"{FOOTER_TEXT}    Page {index}",
            fontsize=8.5,
            fontname="helv",
            color=(0.35, 0.41, 0.5),
            align=fitz.TEXT_ALIGN_CENTER,
        )

    final_output = output_path.with_name(f"{output_path.stem}.tmp.pdf")
    if final_output.exists():
        final_output.unlink()
    doc.save(final_output)
    doc.close()
    if output_path.exists():
        output_path.unlink()
    final_output.rename(output_path)


def main() -> None:
    md_text = SOURCE_MD.read_text(encoding="utf-8")
    html = markdown_to_html(md_text)
    build_pdf(html, OUTPUT_PDF)
    print(f"Created: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()

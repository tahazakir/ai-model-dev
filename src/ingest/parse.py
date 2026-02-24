"""PDF parsing with docling: extract section-aware text from research papers."""

import json
import re
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

from config import PROCESSED_DIR


def remove_latex(text: str) -> str:
    """Remove LaTeX content, keeping only plain text."""
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    text = re.sub(r"\$[^\$]+\$", "", text)
    text = re.sub(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\\[^a-zA-Z\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Clean extracted text: remove LaTeX, images, footnotes."""
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # markdown images
    text = re.sub(r"^\[\^?\d+\].*$", "", text, flags=re.MULTILINE)  # footnotes
    text = remove_latex(text)
    text = re.sub(r"\n{3,}", "\n\n", text)  # collapse blank lines
    return text.strip()


def parse_pdf(pdf_path: Path) -> list[tuple[str, str]]:
    """
    Parse a PDF with docling and return a list of (section_title, text) tuples.
    Uses the document structure for section-aware extraction.
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    result = converter.convert(str(pdf_path))

    # Try structured extraction first
    sections = _extract_sections_structured(result)

    # Fall back to markdown header parsing
    if not sections:
        md = result.document.export_to_markdown()
        sections = _extract_sections_markdown(md)

    # Last resort: full document as one section
    if not sections:
        md = result.document.export_to_markdown()
        cleaned = clean_text(md)
        if cleaned:
            sections = [("Full Document", cleaned)]

    return sections


def save_processed(source_id: str, filename: str, sections: list[tuple[str, str]]) -> Path:
    """Save parsed sections to data/processed/ as JSON."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    processed_path = PROCESSED_DIR / f"{source_id}.json"
    with open(processed_path, "w") as f:
        json.dump(
            {
                "source_id": source_id,
                "filename": filename,
                "sections": [{"title": t, "text": txt} for t, txt in sections],
                "num_sections": len(sections),
            },
            f,
            indent=2,
        )
    return processed_path


def _extract_sections_structured(result) -> list[tuple[str, str]]:
    """Extract sections from docling's document structure."""
    skip_types = {
        "Picture", "Figure", "Image", "Footnote", "Reference", "Caption",
        "Formula", "Equation",
    }

    sections: list[tuple[str, str]] = []
    current_title = None
    current_parts: list[str] = []

    for element, _level in result.document.iterate_items():
        etype = element.__class__.__name__

        if etype in skip_types:
            continue
        if hasattr(element, "label") and element.label:
            label_lower = element.label.lower()
            if any(s in label_lower for s in ["figure", "image", "picture",
                                               "footnote", "caption",
                                               "formula", "equation", "math"]):
                continue

        is_header = etype in ("SectionHeader", "Title", "Heading") or (
            hasattr(element, "label")
            and element.label
            and "heading" in element.label.lower()
        )

        if is_header and hasattr(element, "text"):
            if current_title and current_parts:
                content = clean_text("\n\n".join(current_parts))
                if content:
                    sections.append((current_title, content))
            current_title = element.text.strip()
            current_parts = []
        elif hasattr(element, "text") and element.text:
            text = element.text.strip()
            if text and not (text.startswith("$") or text.startswith("\\")):
                current_parts.append(text)

    # Flush last section
    if current_title and current_parts:
        content = clean_text("\n\n".join(current_parts))
        if content:
            sections.append((current_title, content))

    return sections


def _extract_sections_markdown(md_content: str) -> list[tuple[str, str]]:
    """Fall back: parse markdown headers to extract sections."""
    sections: list[tuple[str, str]] = []
    current_title = None
    current_lines: list[str] = []

    for line in md_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("!["):
            continue
        if re.match(r"^\[\^?\d+\]", stripped):
            continue
        if stripped.startswith("$") or stripped.startswith("\\begin"):
            continue

        header_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if header_match:
            if current_title and current_lines:
                content = clean_text("\n".join(current_lines))
                if content:
                    sections.append((current_title, content))
            current_title = header_match.group(2).strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    if current_title and current_lines:
        content = clean_text("\n".join(current_lines))
        if content:
            sections.append((current_title, content))

    return sections

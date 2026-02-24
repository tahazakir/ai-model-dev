"""Export functionality for research artifacts."""

import csv
import io
import re
from datetime import datetime
from pathlib import Path

from config import OUTPUTS_DIR


def export_markdown(content: str, title: str) -> str:
    """Wrap content in a markdown document with title and timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"# {title}\n\n*Generated: {timestamp}*\n\n{content}"


def export_csv_from_markdown_table(markdown_table: str) -> str:
    """Convert a markdown table to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)

    lines = [line.strip() for line in markdown_table.strip().split("\n") if line.strip()]

    for line in lines:
        # Skip separator lines (e.g., |---|---|)
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        # Parse table row
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells:
            writer.writerow(cells)

    return output.getvalue()


def _sanitize_for_pdf(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents."""
    replacements = {
        "\u2013": "-",   # en-dash
        "\u2014": "--",  # em-dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u2022": "-",   # bullet
        "\u00a0": " ",   # non-breaking space
        "\u2032": "'",   # prime
        "\u2033": '"',   # double prime
        "\u2212": "-",   # minus sign
        "\u00b7": "-",   # middle dot
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Strip any remaining non-latin1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def export_pdf(content: str, title: str) -> bytes:
    """Convert markdown content to PDF using fpdf2."""
    from fpdf import FPDF

    content = _sanitize_for_pdf(content)
    title = _sanitize_for_pdf(title)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, title, ln=True)
    pdf.ln(4)

    # Timestamp
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(6)

    # Helper: reset X to left margin before every multi_cell to guarantee
    # full page width is available (prevents "not enough horizontal space" error)
    l_margin = pdf.l_margin

    def safe_multi_cell(w, h, txt):
        pdf.x = l_margin
        pdf.multi_cell(w, h, txt)

    # Content
    pdf.set_font("Helvetica", size=10)
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue

        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            safe_multi_cell(0, 8, stripped[2:])
            pdf.set_font("Helvetica", size=10)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            safe_multi_cell(0, 7, stripped[3:])
            pdf.set_font("Helvetica", size=10)
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            safe_multi_cell(0, 6, stripped[4:])
            pdf.set_font("Helvetica", size=10)
        elif stripped.startswith("**") and stripped.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            safe_multi_cell(0, 6, stripped[2:-2])
            pdf.set_font("Helvetica", size=10)
        elif stripped.startswith("- "):
            safe_multi_cell(0, 5, f"    {stripped}")
        elif stripped.startswith("|"):
            # Skip separator lines (e.g., |---|---|)
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            # Table row - render each cell on its own line to avoid width overflow
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            pdf.set_font("Helvetica", size=7)
            for cell in cells:
                if cell:
                    safe_multi_cell(0, 4, cell)
            pdf.ln(2)
            pdf.set_font("Helvetica", size=10)
        else:
            safe_multi_cell(0, 5, stripped)

    return bytes(pdf.output())


def save_artifact(content: str, filename: str) -> Path:
    """Save an artifact to the outputs/ directory."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUTS_DIR / filename
    if isinstance(content, bytes):
        filepath.write_bytes(content)
    else:
        filepath.write_text(content)
    return filepath

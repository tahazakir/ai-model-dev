#!/usr/bin/env python3
"""
Script to chunk PDFs using docling and output markdown files with chunk IDs.
"""

from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import PdfFormatOption
import re


def inspect_document_structure(doc_result, pdf_name):
    """
    Print out the document structure to understand what elements we have.
    """
    print(f"\n=== Inspecting structure of {pdf_name} ===")

    element_types = {}
    sample_elements = []

    for element, level in doc_result.document.iterate_items():
        element_type = element.__class__.__name__

        # Count element types
        if element_type not in element_types:
            element_types[element_type] = 0
        element_types[element_type] += 1

        # Collect samples
        if len(sample_elements) < 20:
            text = getattr(element, 'text', '')[:100] if hasattr(element, 'text') else ''
            sample_elements.append({
                'type': element_type,
                'level': level,
                'text': text,
                'label': getattr(element, 'label', None)
            })

    print(f"Element type counts: {element_types}")
    print(f"\nFirst 20 elements:")
    for i, elem in enumerate(sample_elements, 1):
        print(f"  {i}. Type: {elem['type']}, Level: {elem['level']}, Label: {elem['label']}")
        if elem['text']:
            print(f"     Text: {elem['text']}")
    print("=" * 50 + "\n")


def remove_latex(text):
    """
    Remove LaTeX content from text, keeping only plain text.
    """
    # Remove display math ($$...$$)
    text = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL)

    # Remove inline math ($...$)
    text = re.sub(r'\$[^\$]+\$', '', text)

    # Remove LaTeX environments (\begin{...}...\end{...})
    text = re.sub(r'\\begin\{[^}]+\}.*?\\end\{[^}]+\}', '', text, flags=re.DOTALL)

    # Remove LaTeX commands with arguments (\command{...})
    text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', text)

    # Remove standalone LaTeX commands (\command)
    text = re.sub(r'\\[a-zA-Z]+', '', text)

    # Remove LaTeX symbols and special characters
    text = re.sub(r'\\[^a-zA-Z\s]', '', text)

    # Clean up multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    return text.strip()


def chunk_by_markdown_headers(markdown_content):
    """
    Parse markdown content and chunk by headers.
    Returns a list of (title, content) tuples.
    Filters out images, footnotes, and LaTeX.
    """
    chunks = []
    lines = markdown_content.split('\n')

    current_title = None
    current_content = []

    for line in lines:
        # Skip image lines
        if line.strip().startswith('!['):
            continue

        # Skip footnote markers and references
        if re.match(r'^\[\^?\d+\]', line.strip()):
            continue

        # Skip lines that are primarily LaTeX (start with $ or \)
        stripped = line.strip()
        if stripped.startswith('$') or stripped.startswith('\\begin') or stripped.startswith('\\end'):
            continue

        # Check for markdown headers (## or ###)
        header_match = re.match(r'^(#{1,3})\s+(.+)$', line)

        if header_match:
            # Save previous chunk
            if current_title and current_content:
                content_text = '\n'.join(current_content).strip()
                # Filter out inline images and LaTeX from content
                content_text = re.sub(r'!\[.*?\]\(.*?\)', '', content_text)
                content_text = remove_latex(content_text)
                if content_text:  # Only add if there's actual content
                    chunks.append((current_title, content_text))

            # Start new chunk
            current_title = header_match.group(2).strip()
            current_content = []
        else:
            # Add to current chunk
            if current_title:  # Only add if we're in a section
                current_content.append(line)

    # Add last chunk
    if current_title and current_content:
        content_text = '\n'.join(current_content).strip()
        content_text = re.sub(r'!\[.*?\]\(.*?\)', '', content_text)
        content_text = remove_latex(content_text)
        if content_text:
            chunks.append((current_title, content_text))

    return chunks


def chunk_document_by_sections(doc_result):
    """
    Extract chunks from document based on sections/headings.
    Returns a list of (title, content) tuples.
    Filters out images, figures, footnotes, and LaTeX.
    """
    chunks = []
    current_chunk_title = None
    current_chunk_content = []

    # Element types to skip (images, figures, footnotes, formulas, etc.)
    skip_element_types = {'Picture', 'Figure', 'Image', 'Footnote', 'Reference', 'Caption', 'Formula', 'Equation'}

    # Try to iterate through document structure
    for element, level in doc_result.document.iterate_items():
        element_type = element.__class__.__name__

        # Skip unwanted element types
        if element_type in skip_element_types:
            continue

        # Skip if label indicates it's a figure/image/footnote/formula
        if hasattr(element, 'label') and element.label:
            label_lower = element.label.lower()
            if any(skip in label_lower for skip in ['figure', 'image', 'picture', 'footnote', 'caption', 'formula', 'equation', 'math']):
                continue

        # Check for various types of headers/sections
        # Docling uses different element types depending on the document structure
        is_header = (
            element_type in ['SectionHeader', 'Title', 'Heading'] or
            (hasattr(element, 'label') and element.label and 'heading' in element.label.lower())
        )

        if is_header and hasattr(element, 'text'):
            # Save previous chunk if it exists
            if current_chunk_title and current_chunk_content:
                content = '\n\n'.join(current_chunk_content)
                # Remove LaTeX from content
                content = remove_latex(content)
                if content.strip():  # Only add non-empty chunks
                    chunks.append((current_chunk_title, content))

            # Start new chunk
            current_chunk_title = element.text.strip()
            current_chunk_content = []

        # Add content to current chunk (text only, skip LaTeX-heavy text)
        elif hasattr(element, 'text') and element.text:
            text = element.text.strip()
            # Skip if text is mostly LaTeX (starts with $ or \)
            if text and not (text.startswith('$') or text.startswith('\\')):
                current_chunk_content.append(text)

    # Add the last chunk
    if current_chunk_title and current_chunk_content:
        content = '\n\n'.join(current_chunk_content)
        content = remove_latex(content)
        if content.strip():
            chunks.append((current_chunk_title, content))

    return chunks


def process_pdf(pdf_path: Path, output_dir: Path, debug=False):
    """
    Process a single PDF file and create a chunked markdown output.
    """
    print(f"Processing: {pdf_path.name}")

    # Initialize the document converter with options for better column handling
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False  # Set to True if you need OCR
    pipeline_options.do_table_structure = True  # Extract tables properly

    # Enable better reading order detection for multi-column layouts
    # This helps with double-column academic papers
    pipeline_options.images_scale = 1.0  # Don't need high-res images
    pipeline_options.generate_page_images = False  # Skip page images to save processing
    pipeline_options.generate_picture_images = False  # Skip embedded pictures

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    # Convert the document
    result = converter.convert(str(pdf_path))

    # Debug: inspect document structure if requested
    if debug:
        inspect_document_structure(result, pdf_path.name)

    # Try method 1: Extract chunks from document structure
    print("  Attempting to extract chunks from document structure...")
    chunks = chunk_document_by_sections(result)

    # If no structured chunks found, try parsing the markdown export
    if not chunks:
        print("  No structured sections found, trying markdown parsing...")
        markdown_content = result.document.export_to_markdown()
        chunks = chunk_by_markdown_headers(markdown_content)

    # If still no chunks, fall back to full document
    if not chunks:
        print("  No sections detected, exporting full document")
        markdown_content = result.document.export_to_markdown()
        chunks = [("Full Document", markdown_content)]

    print(f"  Found {len(chunks)} chunks")

    # Create output markdown file
    output_filename = pdf_path.stem + "_chunked.md"
    output_path = output_dir / output_filename

    # Write chunks to markdown file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Chunked Document: {pdf_path.name}\n\n")
        f.write(f"Generated from: {pdf_path}\n\n")
        f.write(f"Total chunks: {len(chunks)}\n\n")
        f.write("---\n\n")

        for idx, (title, content) in enumerate(chunks, 1):
            f.write(f"## Chunk {idx}: {title}\n\n")
            f.write(content)
            f.write("\n\n---\n\n")

    print(f"  Created: {output_path}")
    return output_path


def main():
    # Define input PDFs and output directory
    base_dir = Path(__file__).parent
    phase1_dir = base_dir / "phase 1"
    output_dir = base_dir / "phase 1"

    pdf_files = [
        phase1_dir / "Agent Smith.pdf"
    ]

    # Enable debug mode to see document structure
    debug_mode = True  # Set to False to disable debugging output

    # Process each PDF
    for pdf_path in pdf_files:
        if not pdf_path.exists():
            print(f"Warning: {pdf_path} not found, skipping...")
            continue

        try:
            process_pdf(pdf_path, output_dir, debug=debug_mode)
            print()
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {str(e)}")
            import traceback
            traceback.print_exc()
            print()

    print("Processing complete!")


if __name__ == "__main__":
    main()

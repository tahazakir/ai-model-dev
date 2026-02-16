"""Extract metadata for research paper PDFs using DOI lookup via CrossRef
and Semantic Scholar as a fallback for arXiv preprints."""

import json
import re
import time
from pathlib import Path

import httpx
from habanero import Crossref
from pypdf import PdfReader

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_FIELDS = "title,authors,year,venue,externalIds,publicationTypes,publicationVenue"


DATA_DIR = Path(__file__).parent / "data_sources"
OUTPUT_PATH = Path(__file__).parent / "data_manifest.json"

# Manual arXiv ID overrides for papers where automatic extraction fails
ARXIV_OVERRIDES: dict[str, str] = {
    "safedecoding.pdf": "2402.08983",
    "xteaming.pdf": "2504.13203",
}


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 3) -> str:
    """Return concatenated text from the first `max_pages` pages of a PDF."""
    reader = PdfReader(pdf_path)
    pages = reader.pages[:max_pages]
    return "\n".join(page.extract_text() or "" for page in pages)


def find_doi(text: str) -> str | None:
    """Find and return the first DOI in the text, or None."""
    # DOI pattern: 10.XXXX/anything-up-to-whitespace-or-common-delimiters
    match = re.search(r"10\.\d{4,9}/[^\s,;\"'<>]+", text)
    if match:
        # Strip trailing punctuation that may have been captured
        doi = match.group().rstrip(".)")
        return doi
    return None


def find_arxiv_id(text: str) -> str | None:
    """Find and return the first arXiv ID in the text, or None."""
    match = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})(v\d+)?", text, re.IGNORECASE)
    if match:
        return match.group(1)
    # Also try bare pattern like "2310.12345"
    match = re.search(r"\b(\d{4}\.\d{5})\b", text)
    if match:
        return match.group(1)
    return None


def _s2_get(url: str, params: dict | None = None, retries: int = 3) -> dict | None:
    """Make a GET request to Semantic Scholar API with retry on rate-limit / transient errors."""
    with httpx.Client(timeout=15) as client:
        for attempt in range(retries):
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))  # Back off: 3s, 6s
                continue
            break
    return None


def fetch_metadata_from_s2(paper_id: str) -> dict | None:
    """Fetch metadata from Semantic Scholar by paper ID (arXiv ID, DOI, S2 ID, etc.)."""
    data = _s2_get(f"{S2_API_BASE}/paper/{paper_id}", {"fields": S2_FIELDS})
    if not data:
        return None
    return _parse_s2_paper(data)


def search_s2_by_title(title: str) -> dict | None:
    """Search Semantic Scholar by title and return metadata for the best match."""
    clean_title = _normalize(title)
    data = _s2_get(f"{S2_API_BASE}/paper/search", {"query": clean_title, "limit": "5", "fields": S2_FIELDS})
    if not data:
        return None
    items = data.get("data", [])
    if not items:
        return None

    stopwords = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "is", "by", "with"}
    query_words = set(clean_title.split()) - stopwords
    best = None
    best_score = 0
    for item in items:
        ct = item.get("title", "")
        ct_words = set(_normalize(ct).split()) - stopwords
        if not query_words or not ct_words:
            continue
        common = query_words & ct_words
        union = query_words | ct_words
        score = len(common) / len(union)
        if score > best_score:
            best_score = score
            best = item
    if best is None or best_score < 0.55:
        return None
    return _parse_s2_paper(best)


def _parse_s2_paper(data: dict) -> dict:
    """Parse a Semantic Scholar paper object into our metadata dict."""
    authors = [a.get("name", "") for a in data.get("authors", [])]

    ext_ids = data.get("externalIds") or {}
    doi = ext_ids.get("DOI")
    arxiv_id = ext_ids.get("ArXiv")

    venue = data.get("venue") or None
    pub_venue = data.get("publicationVenue")
    if not venue and pub_venue:
        venue = pub_venue.get("name")

    pub_types = data.get("publicationTypes") or []
    paper_type = pub_types[0] if pub_types else None

    return {
        "title": data.get("title"),
        "authors": authors,
        "year": data.get("year"),
        "venue": venue,
        "type": paper_type,
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
        "arxiv_id": arxiv_id,
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
    }


def extract_title(text: str) -> str | None:
    """Heuristic: grab the title from the first substantive lines of the PDF.
    Concatenates lines until hitting an author-like line (contains digits, emails, or affiliations)."""
    skip_prefixes = (
        "arxiv", "published as", "under review", "preprint", "to appear",
        "proceedings of", "accepted", "workshop", "journal of",
    )
    lines = text.splitlines()
    title_parts = []
    collecting = False

    for line in lines:
        line = line.strip()
        if not line or len(line) <= 10:
            if collecting:
                break  # Empty line after title = end of title
            continue
        low = line.lower()
        if any(low.startswith(p) for p in skip_prefixes):
            continue
        if re.match(r"^(january|february|march|april|may|june|july|august|september|october|november|december)\b", low):
            continue
        if re.match(r"^[\d\s,\-–:/©]+$", line):
            continue

        # Stop if this looks like an author line (superscript digits, email, affiliation markers)
        if collecting and re.search(r"\d[,∗†]|\b\d{1}\b.*@|@\w+\.\w+|university|abstract", low):
            break

        title_parts.append(line)
        collecting = True

    return " ".join(title_parts) if title_parts else None


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for comparison."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _clean_pdf_title(title: str) -> str:
    """Clean up PDF extraction artifacts from a title for search queries.
    Fixes broken spacing like 'S AFE' → 'SAFE', 'B ENCH' → 'BENCH',
    'Multi-T urn' → 'Multi-Turn'. Preserves real words like 'A Frontier'."""
    # Only collapse single uppercase char + space + continuation when preceded by
    # a dash or another uppercase letter (i.e. mid-acronym), not at word boundaries
    # e.g. "PKU-S AFE" → "PKU-SAFE", "SORRY-B ENCH" → "SORRY-BENCH"
    cleaned = re.sub(r"(?<=[A-Z\-])([A-Z]) ([A-Za-z]{2,})", r"\1\2", title)
    # Handle chains like "S O R R Y" (consecutive single chars)
    cleaned = re.sub(r"(?<![A-Za-z])([A-Z]) (?=[A-Z] [A-Z])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def search_crossref_by_title(title: str) -> dict | None:
    """Search CrossRef by title and return metadata for the best match."""
    cr = Crossref()
    clean_title = _normalize(title)
    results = cr.works(query_bibliographic=clean_title, limit=5)
    items = results.get("message", {}).get("items", [])
    if not items:
        return None

    # Filter out short stopwords to avoid false matches on generic terms
    stopwords = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "is", "by", "with"}
    query_words = set(clean_title.split()) - stopwords
    best = None
    best_score = 0
    for item in items:
        for ct in item.get("title", []):
            ct_norm = _normalize(ct)
            ct_words = set(ct_norm.split()) - stopwords
            if not query_words or not ct_words:
                continue
            common = query_words & ct_words
            union = query_words | ct_words
            score = len(common) / len(union)
            if score > best_score:
                best_score = score
                best = item
    # Require high Jaccard overlap to avoid false matches
    if best is None or best_score < 0.55:
        return None
    return best


def _parse_crossref_message(msg: dict) -> dict:
    """Parse a CrossRef work message into our metadata dict."""
    authors = []
    for author in msg.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        authors.append(f"{given} {family}".strip())

    year = None
    for date_field in ("published-print", "published-online", "created"):
        parts = msg.get(date_field, {}).get("date-parts", [[]])
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break

    venue = None
    container = msg.get("container-title", [])
    if container:
        venue = container[0]
    elif msg.get("event", {}).get("name"):
        venue = msg["event"]["name"]

    doi = msg.get("DOI")
    return {
        "title": (msg.get("title") or [None])[0],
        "authors": authors,
        "year": year,
        "venue": venue,
        "type": msg.get("type"),
        "doi": doi,
        "doi_url": f"https://doi.org/{doi}" if doi else None,
    }


def fetch_metadata_from_crossref(doi: str) -> dict:
    """Query CrossRef for metadata associated with the given DOI."""
    cr = Crossref()
    result = cr.works(ids=doi)
    return _parse_crossref_message(result["message"])


def process_all_papers(data_dir: Path, output_path: Path) -> None:
    """Process all PDFs in data_dir, write metadata to output_path."""
    pdf_files = sorted(data_dir.glob("*.pdf"))
    results = []
    succeeded = 0
    failed = []

    for pdf_path in pdf_files:
        filename = pdf_path.name
        print(f"Processing: {filename}")

        entry = {
            "filename": filename,
            "title": None,
            "authors": None,
            "year": None,
            "venue": None,
            "type": None,
            "doi": None,
            "doi_url": None,
            "arxiv_id": None,
            "arxiv_url": None,
            "relevance_note": None,
            "status": "ok",
        }

        try:
            text = extract_text_from_pdf(pdf_path)
            doi = find_doi(text)
            arxiv_id = find_arxiv_id(text)
            title = extract_title(text)

            # Apply manual overrides
            if filename in ARXIV_OVERRIDES and ARXIV_OVERRIDES[filename]:
                arxiv_id = ARXIV_OVERRIDES[filename]
            resolved = False

            # Strategy 1: DOI → CrossRef
            if doi:
                print(f"  DOI: {doi}")
                try:
                    metadata = fetch_metadata_from_crossref(doi)
                    entry.update(metadata)
                    resolved = True
                    print(f"  ✓ [CrossRef] {metadata['title']}")
                except Exception:
                    print(f"  ✗ CrossRef lookup failed for DOI")

            # Strategy 2: arXiv ID → Semantic Scholar
            if not resolved and arxiv_id:
                print(f"  arXiv: {arxiv_id}")
                time.sleep(2)  # Respect S2 rate limits (1 req/sec for free tier)
                metadata = fetch_metadata_from_s2(f"ARXIV:{arxiv_id}")
                if metadata:
                    entry.update(metadata)
                    entry["status"] = "matched_by_arxiv"
                    resolved = True
                    print(f"  ✓ [S2/arXiv] {metadata['title']}")
                else:
                    print(f"  ✗ S2 lookup failed for arXiv ID")

            # Strategy 3: Title → Semantic Scholar search
            if not resolved and title:
                clean_title = _clean_pdf_title(title)
                print(f"  Searching by title: {clean_title[:60]}...")
                time.sleep(2)
                metadata = search_s2_by_title(clean_title)
                if metadata:
                    entry.update(metadata)
                    entry["status"] = "matched_by_title"
                    resolved = True
                    print(f"  ✓ [S2/title] {metadata['title']}")

            # Strategy 4: Title → CrossRef search
            if not resolved and title:
                match = search_crossref_by_title(title)
                if match:
                    metadata = _parse_crossref_message(match)
                    entry.update(metadata)
                    entry["status"] = "matched_by_title_crossref"
                    resolved = True
                    print(f"  ✓ [CrossRef/title] {metadata['title']}")

            if resolved:
                succeeded += 1
            else:
                if title:
                    entry["title"] = title
                entry["status"] = "unresolved"
                print(f"  ✗ Could not resolve metadata")
                failed.append(filename)

        except Exception as e:
            entry["status"] = f"error: {e}"
            print(f"  ✗ Error: {e}")
            failed.append(filename)

        results.append(entry)

    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nDone — {succeeded}/{len(pdf_files)} papers resolved")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"Output: {output_path}")


def main():
    process_all_papers(DATA_DIR, OUTPUT_PATH)


if __name__ == "__main__":
    main()

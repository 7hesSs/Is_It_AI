"""
PDF text extraction for the PDF-check pipeline.

Known reliability limits, worth being upfront about:
  - Multi-column academic layouts can extract out of reading order (pypdf
    reads text in the order it's encoded in the PDF, which doesn't always
    match visual column order). The extracted-text preview sent back to the
    frontend exists specifically so a user can catch this rather than
    trusting a score blindly.
  - Scanned/image-only PDFs have no text layer at all - extraction returns
    empty or near-empty text, handled as an explicit error rather than
    silently scoring garbage.
  - References/bibliography sections are stripped via a heading-match
    heuristic, not perfect - a paper with an unconventional heading name
    won't get stripped.
"""
import io
import re

from pypdf import PdfReader

MAX_PAGES = 50

# Matches a line that's just "References", "Bibliography", "Works Cited",
# optionally numbered ("7. References"), on its own line.
REFERENCE_HEADING_RE = re.compile(
    r"^\s*(?:\d+\.?\s*)?(references|bibliography|works cited)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_text(pdf_bytes: bytes) -> tuple[str, dict]:
    """
    Returns (text, metadata) where metadata includes page counts and
    whether the document was truncated, so the router can surface that as
    risk flags.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    pages_to_read = reader.pages[:MAX_PAGES]

    text_parts = []
    for page in pages_to_read:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)

    full_text = "\n".join(text_parts).strip()

    metadata = {
        "total_pages": total_pages,
        "pages_read": len(pages_to_read),
        "truncated_pages": total_pages > MAX_PAGES,
    }
    return full_text, metadata


def strip_references_section(text: str) -> str:
    """
    Truncates at a References/Bibliography heading if one is found in the
    latter half of the document - conservative on purpose, to avoid
    stripping real content from short documents or papers that mention
    "references" earlier in the body text.

    IMPORTANT: call this BEFORE normalize_extracted_text(), not after - it
    relies on the heading sitting alone on its own line, which the
    normalization step deliberately collapses away.
    """
    for match in REFERENCE_HEADING_RE.finditer(text):
        if match.start() > len(text) * 0.5:
            return text[: match.start()].strip()
    return text


def normalize_extracted_text(text: str) -> str:
    """
    Cleans up PDF-extraction artifacts before scoring - critical for
    LaTeX-compiled documents specifically. pypdf (like most PDF text
    extractors) inserts a line break after every VISUAL line, not every
    paragraph, since that's how the PDF's content stream is structured.
    Heavily justified/wrapped LaTeX output means a single sentence often
    spans several of these fragments, frequently with words split by a
    hyphen at the line break (e.g. "informa-\\ntion").

    Left uncleaned, this noise skews both the perplexity signal and the
    classifier, since neither was trained on text full of mid-word line
    breaks - this was the direct cause of normally-written LaTeX documents
    scoring as AI-generated more often than they should.
    """
    # Rejoin words split across a line break by a hyphen: "informa-\ntion" -> "information"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # Collapse a single newline (a mid-paragraph line wrap) into a space,
    # but leave a real paragraph break (blank line / double newline) intact.
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Normalize any run of 3+ newlines down to one standard paragraph break
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of spaces/tabs left behind by justified-text extraction
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()

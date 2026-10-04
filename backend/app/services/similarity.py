"""
Two-document similarity check - compares two documents DIRECTLY against
each other, not against the web or any external corpus. This is an
honestly-scoped alternative to full plagiarism detection: it answers "how
much do these two specific documents overlap," which is what's actually
useful for comparing two students' lab reports or assignments, without
pretending to check against the whole internet.

Two dependency-free signals, both pure stdlib + basic Python:
  1. N-gram (shingle) Jaccard similarity - the headline score. Splits each
     document into overlapping 5-word sequences and measures what fraction
     are shared. This is the same basic technique real plagiarism tools use
     under the hood, and catches copy-paste-with-light-editing well.
     Real limit, not a bug: it will NOT catch a fully paraphrased passage
     that reuses none of the original phrasing.
  2. Matching passages - the actual overlapping text, via difflib's
     sequence matcher, so the result shows exactly what matched rather than
     asking the user to trust a bare percentage.
"""
import re
from difflib import SequenceMatcher

SHINGLE_SIZE = 5
MIN_MATCH_LENGTH = 40  # characters - shorter matches are usually coincidental phrasing
MAX_MATCHES_RETURNED = 15

HIGH_THRESHOLD = 0.4
MEDIUM_THRESHOLD = 0.15


def _normalize_words(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def _shingles(words: list[str], size: int = SHINGLE_SIZE) -> set[str]:
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def compute_similarity(text_a: str, text_b: str) -> float:
    shingles_a = _shingles(_normalize_words(text_a))
    shingles_b = _shingles(_normalize_words(text_b))

    if not shingles_a or not shingles_b:
        return 0.0

    intersection = shingles_a & shingles_b
    union = shingles_a | shingles_b
    return len(intersection) / len(union)


def similarity_verdict(score: float) -> str:
    if score > HIGH_THRESHOLD:
        return "high"
    if score > MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def find_matching_passages(text_a: str, text_b: str) -> list[dict]:
    """
    Returns the actual overlapping passages (verbatim from document A),
    longest first, capped so the response doesn't balloon on two very
    similar documents.
    """
    matcher = SequenceMatcher(None, text_a, text_b, autojunk=False)
    blocks = [b for b in matcher.get_matching_blocks() if b.size >= MIN_MATCH_LENGTH]
    blocks.sort(key=lambda b: b.size, reverse=True)

    passages = []
    for block in blocks[:MAX_MATCHES_RETURNED]:
        passages.append(
            {"text": text_a[block.a : block.a + block.size].strip(), "length": block.size}
        )
    return passages

"""
Semantic (paraphrase) similarity - complements the literal shingle-overlap
check in similarity.py, which only catches matching WORDING. This catches
matching MEANING even when the wording differs substantially: the
"rewrote it in their own words" case the shingle check structurally cannot see.

Deliberately sentence-level, not whole-document-level: a bare
document-to-document similarity score would also fire on two independently
written reports covering the same experiment, since they'd naturally
discuss similar concepts in similar terms. Per-sentence matching, combined
with explicitly REQUIRING low literal overlap for that pair, is what
targets paraphrase specifically rather than "same topic" - a pair that's
both semantically and literally similar is just a regular match the
shingle check already found, and isn't reported again here.
"""
import re
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from app.services.text_detection import split_sentences

SEMANTIC_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SEMANTIC_MATCH_THRESHOLD = 0.72  # cosine similarity above this = likely same meaning
LITERAL_OVERLAP_CEILING = 0.25  # below this word-overlap = wording is genuinely different
MAX_SENTENCES_PER_DOC = 150  # caps embedding cost on very long documents
MAX_MATCHES_RETURNED = 15


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(SEMANTIC_MODEL_NAME)


def _words(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower()).split()


def _word_shingles(words: list[str], size: int = 3) -> set[str]:
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def _literal_overlap(sentence_a: str, sentence_b: str) -> float:
    shingles_a = _word_shingles(_words(sentence_a))
    shingles_b = _word_shingles(_words(sentence_b))
    if not shingles_a or not shingles_b:
        return 0.0
    return len(shingles_a & shingles_b) / len(shingles_a | shingles_b)


def find_paraphrase_matches(text_a: str, text_b: str) -> list[dict]:
    """
    Returns sentence pairs that likely mean the same thing but are worded
    differently enough that the literal shingle check wouldn't catch them.
    """
    sentences_a = split_sentences(text_a)[:MAX_SENTENCES_PER_DOC]
    sentences_b = split_sentences(text_b)[:MAX_SENTENCES_PER_DOC]

    if not sentences_a or not sentences_b:
        return []

    model = _load_model()
    embeddings_a = model.encode(sentences_a, convert_to_numpy=True, normalize_embeddings=True)
    embeddings_b = model.encode(sentences_b, convert_to_numpy=True, normalize_embeddings=True)

    # Embeddings are normalized, so a dot product IS cosine similarity here
    similarity_matrix = embeddings_a @ embeddings_b.T

    matches = []
    for i, sentence_a in enumerate(sentences_a):
        best_j = int(np.argmax(similarity_matrix[i]))
        best_score = float(similarity_matrix[i, best_j])

        if best_score < SEMANTIC_MATCH_THRESHOLD:
            continue

        sentence_b = sentences_b[best_j]
        if _literal_overlap(sentence_a, sentence_b) > LITERAL_OVERLAP_CEILING:
            continue  # already caught by the literal check - not a distinct "paraphrase" finding

        matches.append(
            {
                "sentence_a": sentence_a,
                "sentence_b": sentence_b,
                "semantic_similarity": round(best_score, 4),
            }
        )

    matches.sort(key=lambda m: m["semantic_similarity"], reverse=True)
    return matches[:MAX_MATCHES_RETURNED]


def compute_semantic_overlap_score(text_a: str, paraphrase_matches: list[dict]) -> float:
    """
    Headline number: fraction of document A's sentences that found a likely
    paraphrase match in document B. Shown ALONGSIDE the literal similarity
    score, never blended into it - they answer different questions, and
    combining them into one number would hide which kind of overlap was found.
    """
    sentences_a = split_sentences(text_a)[:MAX_SENTENCES_PER_DOC]
    if not sentences_a:
        return 0.0
    return len(paraphrase_matches) / len(sentences_a)

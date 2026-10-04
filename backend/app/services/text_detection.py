"""
Text AI-detection service.

Combines three signals into one ai_probability:
  1. GLYPH classifier    - DeBERTa-v3-based, trained across 14 AI model
                            families from GPT-2 through GPT-4 (primary signal)
  2. Perplexity          - how "surprised" a language model is by the text
  3. Burstiness          - variance in sentence length

Models are loaded lazily on first request and cached.

Model history: this originally used roberta-base-openai-detector, which is
OpenAI's own GPT-2-era detector from 2019. Multiple independent sources
confirm it performs poorly on modern LLM output (ChatGPT, GPT-4, Claude,
Gemini) - it was trained before any of those existed. GLYPH is actively
documented against current model families and is a drop-in replacement
using the same AutoModelForSequenceClassification pattern.
"""
import re
import math
from functools import lru_cache

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    GPT2LMHeadModel,
    GPT2TokenizerFast,
)

TEXT_CLASSIFIER_MODEL_NAME = "ogmatrixllm/glyph-v1.1"
PERPLEXITY_MODEL_NAME = "gpt2"

MIN_TEXT_LENGTH = 50  # characters - below this, scores are unreliable

# Sentence-level highlighting is capped so a very long document doesn't
# turn into dozens of seconds of CPU inference on a free/basic-tier host -
# the overall document score from analyze_text() always covers the full
# text regardless; this cap only limits how much gets individually
# highlighted.
MAX_SENTENCES_FOR_HIGHLIGHTING = 80

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Terms to match against the model's own label names to find the "AI" class,
# since different models name it differently ("fake", "ai", "generated", etc).
# Keeps this code working if the model is swapped again later.
AI_LABEL_TERMS = ("ai", "fake", "generated", "machine", "synthetic")


@lru_cache(maxsize=1)
def _load_text_classifier():
    tokenizer = AutoTokenizer.from_pretrained(TEXT_CLASSIFIER_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(TEXT_CLASSIFIER_MODEL_NAME)
    model.eval()
    return tokenizer, model


@lru_cache(maxsize=1)
def _load_perplexity_model():
    tokenizer = GPT2TokenizerFast.from_pretrained(PERPLEXITY_MODEL_NAME)
    model = GPT2LMHeadModel.from_pretrained(PERPLEXITY_MODEL_NAME)
    model.eval()
    return tokenizer, model


def _find_ai_label_index(id2label: dict) -> int:
    for i, label in id2label.items():
        if any(term in label.lower() for term in AI_LABEL_TERMS):
            return i
    # Fallback: binary classifiers conventionally put the positive class
    # (here, "AI-generated") at index 1 if label names don't match anything
    # recognizable.
    return 1


def _classifier_ai_probability(text: str) -> float:
    tokenizer, model = _load_text_classifier()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]

    ai_index = _find_ai_label_index(model.config.id2label)
    return float(probs[ai_index])


def _perplexity(text: str) -> float:
    tokenizer, model = _load_perplexity_model()
    encodings = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024)
    input_ids = encodings.input_ids

    if input_ids.size(1) < 2:
        return float("nan")

    with torch.no_grad():
        outputs = model(input_ids, labels=input_ids)
        neg_log_likelihood = outputs.loss.item()

    return math.exp(neg_log_likelihood)


def _burstiness(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) < 2:
        return 0.0

    lengths = [len(s.split()) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    if mean_len == 0:
        return 0.0

    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)
    return std_dev / mean_len


def _perplexity_to_score(perplexity: float) -> float:
    if math.isnan(perplexity):
        return 0.5
    midpoint = 30.0
    steepness = 0.08
    return 1 / (1 + math.exp(steepness * (perplexity - midpoint)))


def _burstiness_to_score(burstiness: float) -> float:
    score = 1 - min(burstiness / 0.6, 1.0)
    return max(0.0, score)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def score_sentences(sentences: list[str]) -> list[float]:
    """
    Scores all sentences in ONE batched forward pass through the classifier,
    rather than one pass per sentence - meaningfully faster on CPU, which
    matters for a free/basic-tier deployment with no GPU.
    """
    if not sentences:
        return []

    tokenizer, model = _load_text_classifier()
    inputs = tokenizer(
        sentences, return_tensors="pt", truncation=True, max_length=256, padding=True
    )
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)

    ai_index = _find_ai_label_index(model.config.id2label)
    return [float(p[ai_index]) for p in probs]


def get_sentence_breakdown(text: str) -> tuple[list[dict], bool]:
    """
    Returns (sentence_scores, was_truncated). was_truncated is True when the
    document had more sentences than MAX_SENTENCES_FOR_HIGHLIGHTING - the
    router surfaces this as a risk flag so the UI can be upfront that
    highlighting only covers part of a very long document.
    """
    all_sentences = split_sentences(text)
    truncated = len(all_sentences) > MAX_SENTENCES_FOR_HIGHLIGHTING
    sentences = all_sentences[:MAX_SENTENCES_FOR_HIGHLIGHTING]

    if not sentences:
        return [], False

    scores = score_sentences(sentences)
    breakdown = [
        {"text": sentence, "ai_probability": round(score, 4)}
        for sentence, score in zip(sentences, scores)
    ]
    return breakdown, truncated


def analyze_text(text: str) -> dict:
    text = text.strip()

    classifier_score = _classifier_ai_probability(text)
    perplexity = _perplexity(text)
    burstiness = _burstiness(text)

    perplexity_score = _perplexity_to_score(perplexity)
    burstiness_score = _burstiness_to_score(burstiness)
    heuristic_score = 0.5 * perplexity_score + 0.5 * burstiness_score

    # GLYPH is documented at ~98.85% accuracy across GPT-2 through GPT-4
    # families, far more trustworthy standalone than the old GPT-2-era
    # RoBERTa detector was - so it now carries most of the weight, with
    # perplexity/burstiness as a lighter secondary signal rather than a
    # near-equal partner.
    ai_probability = 0.85 * classifier_score + 0.15 * heuristic_score

    risk_flags = []
    if perplexity_score > 0.75:
        risk_flags.append("low_perplexity")
    if burstiness_score > 0.75:
        risk_flags.append("low_sentence_variance")
    if len(text) < MIN_TEXT_LENGTH:
        risk_flags.append("short_text_low_reliability")

    return {
        "ai_probability": round(ai_probability, 4),
        "components": {
            "classifier_score": round(classifier_score, 4),
            "perplexity": round(perplexity, 2) if not math.isnan(perplexity) else None,
            "perplexity_score": round(perplexity_score, 4),
            "burstiness": round(burstiness, 4),
            "burstiness_score": round(burstiness_score, 4),
        },
        "risk_flags": risk_flags,
    }

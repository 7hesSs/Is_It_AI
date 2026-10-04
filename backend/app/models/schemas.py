from typing import Optional
from pydantic import BaseModel, Field


class DetectionComponents(BaseModel):
    """Sub-scores that fed into the final ai_probability, for transparency."""
    model_config = {"extra": "allow"}


class DetectionResult(BaseModel):
    id: Optional[int] = Field(
        default=None, description="Scan history row id, used to request a PDF report"
    )
    media_type: str = Field(..., description="'text' | 'image' | 'video' | 'pdf'")
    ai_probability: float = Field(..., ge=0, le=1, description="0 = human, 1 = AI")
    confidence: str = Field(..., description="'low' | 'medium' | 'high'")
    components: dict = Field(default_factory=dict, description="Per-signal sub-scores")
    risk_flags: list[str] = Field(default_factory=list)
    extracted_text: Optional[str] = Field(
        default=None,
        description="The exact text that was scored - only set for the PDF "
        "pipeline, so the user can verify extraction didn't mangle anything.",
    )
    sentences: Optional[list[dict]] = Field(
        default=None,
        description="Per-sentence AI-probability scores for highlighting. "
        "Set for text and pdf media types only.",
    )


class SimilarityResult(BaseModel):
    id: Optional[int] = Field(
        default=None, description="Scan history row id, used to request a PDF report"
    )
    similarity_score: float = Field(..., ge=0, le=1, description="Literal wording overlap")
    verdict: str = Field(..., description="'low' | 'medium' | 'high'")
    matching_passages: list[dict] = Field(default_factory=list)
    semantic_overlap_score: float = Field(
        default=0.0, ge=0, le=1, description="Fraction of sentences with a likely paraphrase match"
    )
    paraphrase_matches: list[dict] = Field(
        default_factory=list,
        description="Sentence pairs that likely mean the same thing but are worded differently",
    )
    document_a_label: str
    document_b_label: str


def confidence_bucket(ai_probability: float) -> str:
    """Turn a raw probability into a human-readable confidence bucket.

    Deliberately conservative near 0.5 — that's where detectors are least reliable.
    """
    distance_from_uncertain = abs(ai_probability - 0.5)
    if distance_from_uncertain > 0.35:
        return "high"
    if distance_from_uncertain > 0.15:
        return "medium"
    return "low"

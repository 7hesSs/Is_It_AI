from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.models.schemas import DetectionResult, confidence_bucket
from app.services.text_detection import analyze_text, get_sentence_breakdown, MIN_TEXT_LENGTH
from app.services import cache
from app.services import scans as scans_service
from app.routers.auth import get_current_user

router = APIRouter()

MAX_TEXT_LENGTH = 20_000
LABEL_PREVIEW_LENGTH = 80


class TextAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1, description="The text to analyze")


def _make_label(text: str) -> str:
    preview = text[:LABEL_PREVIEW_LENGTH].replace("\n", " ").strip()
    return preview + "…" if len(text) > LABEL_PREVIEW_LENGTH else preview


@router.post("/text", response_model=DetectionResult)
def analyze_text_endpoint(
    request: TextAnalysisRequest, user: dict = Depends(get_current_user)
):
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Text is too long ({len(text)} characters). "
            f"Max is {MAX_TEXT_LENGTH} - try analyzing an excerpt instead.",
        )

    cache_key = cache.make_key(text.encode("utf-8"))
    cached = cache.get(cache_key)
    if cached:
        response = DetectionResult(**cached)
    else:
        result = analyze_text(text)
        sentences, sentences_truncated = get_sentence_breakdown(text)

        risk_flags = list(result["risk_flags"])
        if sentences_truncated:
            risk_flags.append("sentence_highlighting_partial")

        response = DetectionResult(
            media_type="text",
            ai_probability=result["ai_probability"],
            confidence=confidence_bucket(result["ai_probability"]),
            components=result["components"],
            risk_flags=risk_flags,
            sentences=sentences,
        )
        cache.set(cache_key, response.model_dump())

    scan_id = scans_service.save_scan(
        user["id"], "text", _make_label(text), response.model_dump()
    )
    response.id = scan_id
    return response

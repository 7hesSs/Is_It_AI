from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from app.models.schemas import SimilarityResult
from app.services import pdf_extraction
from app.services import similarity as similarity_service
from app.services import semantic_similarity
from app.services import scans as scans_service
from app.services.text_detection import MIN_TEXT_LENGTH
from app.routers.auth import get_current_user
from app.routers.pdf import MAX_FILE_SIZE_BYTES, ALLOWED_CONTENT_TYPES

router = APIRouter()


def _extract_clean_text(pdf_bytes: bytes) -> str:
    raw_text, _ = pdf_extraction.extract_text(pdf_bytes)
    text = pdf_extraction.strip_references_section(raw_text)
    return pdf_extraction.normalize_extracted_text(text)


@router.post("/similarity", response_model=SimilarityResult)
async def analyze_similarity_endpoint(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    for f in (file_a, file_b):
        if f.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{f.content_type}'. Only PDF files are accepted.",
            )

    bytes_a = await file_a.read()
    bytes_b = await file_b.read()

    for b in (bytes_a, bytes_b):
        if len(b) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"A file is too large. Max size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
            )
        if not b:
            raise HTTPException(status_code=400, detail="One of the files is empty.")

    try:
        text_a = _extract_clean_text(bytes_a)
        text_b = _extract_clean_text(bytes_b)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read one of these PDFs: {exc}")

    if len(text_a) < MIN_TEXT_LENGTH or len(text_b) < MIN_TEXT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="Could not extract enough readable text from one of these PDFs. "
            "It may be scanned/image-only.",
        )

    score = similarity_service.compute_similarity(text_a, text_b)
    verdict = similarity_service.similarity_verdict(score)
    passages = similarity_service.find_matching_passages(text_a, text_b)

    paraphrase_matches = semantic_similarity.find_paraphrase_matches(text_a, text_b)
    semantic_score = semantic_similarity.compute_semantic_overlap_score(text_a, paraphrase_matches)

    label_a = file_a.filename or "Document A"
    label_b = file_b.filename or "Document B"

    response = SimilarityResult(
        similarity_score=round(score, 4),
        verdict=verdict,
        matching_passages=passages,
        semantic_overlap_score=round(semantic_score, 4),
        paraphrase_matches=paraphrase_matches,
        document_a_label=label_a,
        document_b_label=label_b,
    )

    # Reuses the same generic scan-history storage as the other pipelines -
    # ai_probability/confidence columns hold the similarity score/verdict
    # here instead, and the similarity-specific data (labels, passages)
    # goes in the schema-less components dict.
    scan_id = scans_service.save_scan(
        user["id"],
        "similarity",
        f"{label_a} vs {label_b}",
        {
            "ai_probability": response.similarity_score,
            "confidence": response.verdict,
            "components": {
                "document_a_label": label_a,
                "document_b_label": label_b,
                "matching_passages": passages,
                "semantic_overlap_score": response.semantic_overlap_score,
                "paraphrase_matches": paraphrase_matches,
            },
            "risk_flags": [],
        },
    )
    response.id = scan_id

    return response

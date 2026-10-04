from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from app.models.schemas import DetectionResult, confidence_bucket
from app.services.text_detection import analyze_text, get_sentence_breakdown, MIN_TEXT_LENGTH
from app.services import pdf_extraction
from app.services import cache
from app.services import scans as scans_service
from app.routers.auth import get_current_user
from app.routers.text import MAX_TEXT_LENGTH

router = APIRouter()

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("/pdf", response_model=DetectionResult)
async def analyze_pdf_endpoint(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Only PDF files are accepted.",
        )

    pdf_bytes = await file.read()

    if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        raw_text, pdf_meta = pdf_extraction.extract_text(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read this PDF: {exc}")

    text = pdf_extraction.strip_references_section(raw_text)
    text = pdf_extraction.normalize_extracted_text(text)

    if len(text.strip()) < MIN_TEXT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="Could not extract readable text from this PDF. It may be a "
            "scanned document without a text layer, or contain only images.",
        )

    extra_flags = []
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        extra_flags.append("pdf_truncated_long_document")
    if pdf_meta["truncated_pages"]:
        extra_flags.append("pdf_truncated_long_document")

    cache_key = cache.make_key(pdf_bytes)
    cached = cache.get(cache_key)
    if cached:
        response = DetectionResult(**cached)
    else:
        result = analyze_text(text)
        sentences, sentences_truncated = get_sentence_breakdown(text)
        if sentences_truncated:
            extra_flags.append("sentence_highlighting_partial")

        response = DetectionResult(
            media_type="pdf",
            ai_probability=result["ai_probability"],
            confidence=confidence_bucket(result["ai_probability"]),
            components=result["components"],
            risk_flags=list(dict.fromkeys(result["risk_flags"] + extra_flags)),
            extracted_text=text,
            sentences=sentences,
        )
        cache.set(cache_key, response.model_dump())

    label = file.filename or "Uploaded PDF"
    scan_id = scans_service.save_scan(user["id"], "pdf", label, response.model_dump())
    response.id = scan_id
    return response

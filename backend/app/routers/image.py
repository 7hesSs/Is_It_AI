from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from app.models.schemas import DetectionResult, confidence_bucket
from app.services import image_detection
from app.services import cache
from app.services import scans as scans_service
from app.services import thumbnails
from app.routers.auth import get_current_user

router = APIRouter()

MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


@router.post("/image", response_model=DetectionResult)
async def analyze_image_endpoint(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Decode once up front - needed for the thumbnail regardless of whether
    # the inference result itself comes from cache.
    try:
        image = image_detection.load_image(image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not process image: {exc}")

    cache_key = cache.make_key(image_bytes)
    cached = cache.get(cache_key)
    if cached:
        response = DetectionResult(**cached)
    else:
        result = image_detection.analyze_image_object(image)
        response = DetectionResult(
            media_type="image",
            ai_probability=result["ai_probability"],
            confidence=confidence_bucket(result["ai_probability"]),
            components=result["components"],
            risk_flags=result["risk_flags"],
        )
        cache.set(cache_key, response.model_dump())

    label = file.filename or "Uploaded image"
    thumbnail = thumbnails.make_thumbnail_data_url(image)
    scan_id = scans_service.save_scan(
        user["id"], "image", label, response.model_dump(), thumbnail=thumbnail
    )
    response.id = scan_id
    return response

import io

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from app.routers.auth import get_current_user
from app.services import scans as scans_service
from app.services import report_generation

router = APIRouter()

MAX_LIMIT = 50


@router.get("/scans")
def list_scans(limit: int = scans_service.DEFAULT_HISTORY_LIMIT, user: dict = Depends(get_current_user)):
    limit = max(1, min(limit, MAX_LIMIT))
    return scans_service.get_recent_scans(user["id"], limit=limit)


@router.get("/scans/{scan_id}")
def get_scan(scan_id: int, user: dict = Depends(get_current_user)):
    scan = scans_service.get_scan_by_id(user["id"], scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.get("/scans/{scan_id}/report")
def download_scan_report(scan_id: int, user: dict = Depends(get_current_user)):
    scan = scans_service.get_scan_by_id(user["id"], scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    pdf_bytes = report_generation.generate_report_pdf(scan)

    # StreamingResponse + explicit Content-Length, rather than a bare
    # Response(content=bytes) - more robust for binary downloads when a
    # custom BaseHTTPMiddleware (our rate limiter) sits in front of every
    # request, a known trouble spot for binary response bodies in some
    # Starlette/uvicorn version combinations.
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="is-it-ai-report-{scan_id}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )

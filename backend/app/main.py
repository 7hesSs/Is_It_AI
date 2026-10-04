import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.middleware.rate_limit import RateLimitMiddleware
from app.db import init_db

logger = logging.getLogger("ai_detector")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI Content Detector",
    description="Detects AI-generated text, images, and video",
    version="0.1.0",
)

init_db()

_default_origins = "http://localhost:5173,http://localhost:3000"
allowed_origins = os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong processing that request."},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


from app.routers import auth, text, image, video, pdf, similarity, scans

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(text.router, prefix="/analyze", tags=["text"])
app.include_router(image.router, prefix="/analyze", tags=["image"])
app.include_router(video.router, prefix="/analyze", tags=["video"])
app.include_router(pdf.router, prefix="/analyze", tags=["pdf"])
app.include_router(similarity.router, prefix="/analyze", tags=["similarity"])
app.include_router(scans.router, tags=["scans"])

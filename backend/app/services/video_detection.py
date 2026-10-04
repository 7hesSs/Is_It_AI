"""
Video AI-detection service.

Samples ~1 frame/second via OpenCV, runs each through the image pipeline,
aggregates per-frame scores. Frame count is capped so a single request
can't tie up the process indefinitely on a long video.
"""
import cv2
from PIL import Image

from app.services.image_detection import analyze_image_object

TARGET_SAMPLE_FPS = 1.0
MAX_FRAMES_TO_PROCESS = 60


def extract_frames(video_path: str, target_fps: float = TARGET_SAMPLE_FPS) -> list[Image.Image]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(
            "Could not open video file - it may be corrupt or in an unsupported format."
        )

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(video_fps / target_fps))

    frames = []
    frame_index = 0
    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break

            if frame_index % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(frame_rgb))
                if len(frames) >= MAX_FRAMES_TO_PROCESS:
                    break

            frame_index += 1
    finally:
        cap.release()

    return frames


def extract_first_frame(video_path: str) -> Image.Image | None:
    """
    Lightweight single-frame grab, used for the thumbnail when a video hit
    the result cache (identical file re-uploaded) and the full frame
    sampling in analyze_video() never runs.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    try:
        ret, frame_bgr = cap.read()
        if not ret:
            return None
        return Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    finally:
        cap.release()


def analyze_video(video_path: str, progress_callback=None, on_first_frame=None) -> dict:
    frames = extract_frames(video_path)
    if not frames:
        raise ValueError("No frames could be extracted from this video.")

    if on_first_frame:
        on_first_frame(frames[0])

    total = len(frames)
    frame_scores = []

    for i, frame in enumerate(frames):
        frame_result = analyze_image_object(frame)
        frame_scores.append(frame_result["ai_probability"])
        if progress_callback:
            progress_callback(i + 1, total)

    mean_score = sum(frame_scores) / len(frame_scores)
    variance = sum((s - mean_score) ** 2 for s in frame_scores) / len(frame_scores)
    std_dev = variance ** 0.5

    risk_flags = []
    if std_dev > 0.25:
        risk_flags.append("inconsistent_frame_scores")
    if mean_score > 0.75:
        risk_flags.append("high_average_ai_score")
    if total < 3:
        risk_flags.append("very_short_video_low_reliability")

    return {
        "ai_probability": round(mean_score, 4),
        "components": {
            "frames_analyzed": total,
            "frame_score_mean": round(mean_score, 4),
            "frame_score_std_dev": round(std_dev, 4),
            "frame_score_min": round(min(frame_scores), 4),
            "frame_score_max": round(max(frame_scores), 4),
        },
        "risk_flags": risk_flags,
    }

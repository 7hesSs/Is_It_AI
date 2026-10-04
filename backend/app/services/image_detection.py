"""
Image AI-detection service.

Combines two signals:
  1. ViT classifier - distinguishes real photos from AI-generated images
  2. FFT analysis    - periodic high-frequency artifacts from diffusion/GAN
                        upsampling (secondary signal, low weight - see note below)

Model history: this originally used umm-maybe/AI-image-detector, an older
demo-era model that generalizes poorly to current diffusion models
(Midjourney, SDXL, Flux). An attempted swap to husseinelsaadi/aidetect-vit-b16
failed - that repo turned out to be a raw research artifact dump (multiple
experiment checkpoints in subfolders), not a properly packaged model, and
is missing preprocessor_config.json entirely. Settled on Organika/sdxl-detector
instead: a properly packaged Swin Transformer (config.json, model.safetensors,
preprocessor_config.json all present at the repo root, confirmed loadable),
fine-tuned from the original umm-maybe model specifically on SDXL-generated
images. Honest caveat from its own model card: it's optimized for SDXL
specifically and may underperform on other generators (Midjourney, Flux,
older GANs) - a real improvement, not a universal fix.

The FFT weight was also reduced from 0.25 to 0.15. It was an uncalibrated
heuristic guess from the start, with no real data behind its threshold -
likely contributing to the wrong-verdict complaints as much as the old
classifier was. Worth revisiting with real calibration data if accuracy
still isn't where you want it.
"""
import io
import math
from functools import lru_cache

import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch

IMAGE_CLASSIFIER_MODEL_NAME = "Organika/sdxl-detector"

MAX_IMAGE_DIMENSION = 2048

AI_LABEL_TERMS = ("artificial", "ai", "fake", "generated", "synthetic")


@lru_cache(maxsize=1)
def _load_image_classifier():
    processor = AutoImageProcessor.from_pretrained(IMAGE_CLASSIFIER_MODEL_NAME)
    model = AutoModelForImageClassification.from_pretrained(IMAGE_CLASSIFIER_MODEL_NAME)
    model.eval()
    return processor, model


def load_image(image_bytes: bytes) -> Image.Image:
    """Public so callers (routers) can decode once and reuse the image for
    both inference and thumbnail generation, rather than decoding twice."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if max(image.size) > MAX_IMAGE_DIMENSION:
        image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
    return image


def _find_ai_label_index(id2label: dict) -> int:
    for i, label in id2label.items():
        if any(term in label.lower() for term in AI_LABEL_TERMS):
            return i
    return 1  # fallback: conventional positive-class index


def _classifier_ai_probability(image: Image.Image) -> float:
    processor, model = _load_image_classifier()
    inputs = processor(images=image, return_tensors="pt")

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]

    ai_index = _find_ai_label_index(model.config.id2label)
    return float(probs[ai_index])


def _fft_artifact_score(image: Image.Image) -> float:
    grayscale_resized = image.convert("L").resize((256, 256))
    resized = np.array(grayscale_resized, dtype=np.float64)

    fft = np.fft.fft2(resized)
    fft_shifted = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shifted)

    h, w = magnitude.shape
    center_y, center_x = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    radius = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    max_radius = min(center_x, center_y)

    ring_mask = (radius > 0.4 * max_radius) & (radius < 0.9 * max_radius)

    total_energy = magnitude.sum()
    if total_energy == 0:
        return 0.0

    ring_energy = magnitude[ring_mask].sum()
    ring_ratio = ring_energy / total_energy

    midpoint = 0.35
    steepness = 15.0
    score = 1 / (1 + math.exp(-steepness * (ring_ratio - midpoint)))
    return float(score)


def analyze_image_object(image: Image.Image) -> dict:
    """
    Runs the ViT classifier and FFT analysis on an already-loaded PIL Image.
    Split out so the video pipeline can call this directly on extracted
    frames without an encode/decode round-trip.
    """
    classifier_score = _classifier_ai_probability(image)
    fft_score = _fft_artifact_score(image)

    ai_probability = 0.85 * classifier_score + 0.15 * fft_score

    risk_flags = []
    if fft_score > 0.75:
        risk_flags.append("high_frequency_grid_pattern")
    if classifier_score > 0.85:
        risk_flags.append("strong_classifier_match")

    return {
        "ai_probability": round(ai_probability, 4),
        "components": {
            "classifier_score": round(classifier_score, 4),
            "fft_score": round(fft_score, 4),
        },
        "risk_flags": risk_flags,
    }


def analyze_image(image_bytes: bytes) -> dict:
    image = load_image(image_bytes)
    return analyze_image_object(image)

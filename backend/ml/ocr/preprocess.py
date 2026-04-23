"""
Image preprocessing pipeline for OCR.

Enhanced pipeline for low-quality scans:
  load → upscale (if small) → grayscale → denoise → adaptive threshold → deskew

Supports PDF (all pages via pdf2image) and image files (OpenCV-readable).
"""

import logging
from typing import List

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load — all pages
# ---------------------------------------------------------------------------

def load_all_pages(input_path: str, dpi: int = 200) -> List[np.ndarray]:
    """Load every page of a PDF (or a single image) as BGR numpy arrays."""
    if input_path.lower().endswith(".pdf"):
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image is not installed. Run: pip install pdf2image\n"
                "Also requires poppler: brew install poppler"
            )
        try:
            pil_pages = convert_from_path(input_path, dpi=dpi)
        except Exception as exc:
            log.error("pdf2image failed to convert %s: %s", input_path, exc)
            raise

        pages = [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in pil_pages]
        log.info("[Preprocess] Loaded %d page(s) from PDF: %s", len(pages), input_path)
        return pages

    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"Unable to read image: {input_path}")
    log.info("[Preprocess] Loaded image: %s — shape %s", input_path, img.shape)
    return [img]


def load_image(input_path: str) -> np.ndarray:
    """Legacy single-page helper."""
    return load_all_pages(input_path)[0]


# ---------------------------------------------------------------------------
# Enhancement steps
# ---------------------------------------------------------------------------

def to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def upscale_if_small(image: np.ndarray, min_width: int = 1200) -> np.ndarray:
    """Scale up images that are too small for reliable OCR."""
    h, w = image.shape[:2]
    if w < min_width:
        scale = min_width / w
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        log.debug("[Preprocess] Upscaled image: %dx%d → %dx%d", w, h, new_w, new_h)
    return image


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE contrast enhancement — improves faint text on scanned docs."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(image)


def denoise(image: np.ndarray, h: int = 7) -> np.ndarray:
    """Non-local means denoising — lighter h value preserves text edges."""
    return cv2.fastNlMeansDenoising(image, h=h)


def adaptive_threshold(image: np.ndarray) -> np.ndarray:
    """Adaptive binarisation — handles uneven lighting across scanned pages.

    Falls back to Otsu's global threshold if adaptive produces poor results
    (measured by text pixel ratio).
    """
    adaptive = cv2.adaptiveThreshold(
        image, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )

    # Sanity check: if >95% or <5% of pixels are white, fall back to Otsu
    white_ratio = np.sum(adaptive == 255) / adaptive.size
    if white_ratio > 0.95 or white_ratio < 0.05:
        log.debug("[Preprocess] Adaptive threshold produced extreme result (%.1f%%), using Otsu", white_ratio * 100)
        blur = cv2.GaussianBlur(image, (5, 5), 0)
        _, adaptive = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return adaptive


def deskew(image: np.ndarray) -> np.ndarray:
    """Correct rotation using white-pixel moments."""
    coords = np.column_stack(np.where(image > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.3:        # skip sub-0.3° corrections
        return image
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    log.debug("[Preprocess] Deskew applied: %.2f°", angle)
    return rotated


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def preprocess_page(bgr_image: np.ndarray) -> np.ndarray:
    """Full preprocessing pipeline for a single page.

    Steps: upscale → grayscale → contrast → denoise → adaptive threshold → deskew
    Returns a binary (black text on white) grayscale numpy array.
    """
    img = upscale_if_small(bgr_image)
    gray = to_grayscale(img)
    enhanced = enhance_contrast(gray)
    denoised = denoise(enhanced)
    thresh = adaptive_threshold(denoised)
    cleaned = deskew(thresh)
    return cleaned


def preprocess_image(input_path: str) -> np.ndarray:
    """Legacy single-page entry-point (kept for compatibility)."""
    img = load_image(input_path)
    return preprocess_page(img)

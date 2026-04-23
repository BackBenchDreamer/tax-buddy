"""
Image preprocessing utilities for OCR.

Key fix: load_all_pages() returns ALL pages of a PDF,
not just the first page.
"""

import logging
from typing import List

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Load — all pages
# ---------------------------------------------------------------------------

def load_all_pages(input_path: str) -> List[np.ndarray]:
    """Load every page of a PDF (or a single image) as BGR numpy arrays.

    Returns a list of images — one per page.
    """
    if input_path.lower().endswith(".pdf"):
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image is not installed. Run: pip install pdf2image\n"
                "Also requires poppler: brew install poppler"
            )

        try:
            pil_pages = convert_from_path(input_path, dpi=200)
        except Exception as exc:
            log.error("pdf2image failed to convert %s: %s", input_path, exc)
            raise

        pages = []
        for pil_img in pil_pages:
            bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            pages.append(bgr)

        log.info("Loaded %d page(s) from PDF: %s", len(pages), input_path)
        return pages

    else:
        img = cv2.imread(input_path)
        if img is None:
            raise FileNotFoundError(f"Unable to read image: {input_path}")
        log.info("Loaded image: %s — shape %s", input_path, img.shape)
        return [img]


def load_image(input_path: str) -> np.ndarray:
    """Load only the first page (legacy compatibility)."""
    return load_all_pages(input_path)[0]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image  # already grayscale
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise(image: np.ndarray, h: int = 7) -> np.ndarray:
    """Light non-local means denoising. Lower h preserves text details."""
    return cv2.fastNlMeansDenoising(image, h=h)


def threshold(image: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(image, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def deskew(image: np.ndarray) -> np.ndarray:
    coords = np.column_stack(np.where(image > 0))
    if coords.size == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return image
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def preprocess_image(input_path: str) -> np.ndarray:
    """Legacy single-page pipeline (kept for compatibility)."""
    img = load_image(input_path)
    gray = to_grayscale(img)
    denoised = denoise(gray)
    thresh = threshold(denoised)
    return deskew(thresh)

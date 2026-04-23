"""
Image preprocessing pipeline: denoising, deskewing, binarization.
Handles both PDF (converted to images) and direct image uploads.
"""
import io
import math
from pathlib import Path
from typing import Union
import numpy as np
from PIL import Image
from loguru import logger

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available; skipping deskew/denoise")

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning("pdf2image not available; PDFs will be opened as images directly")


def load_document(file_path: Union[str, Path]) -> list[Image.Image]:
    """Load a document (PDF or image) into a list of PIL Images."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        if PDF2IMAGE_AVAILABLE:
            try:
                images = convert_from_path(str(path), dpi=300, fmt="png")
                logger.info(f"Converted PDF {path.name} to {len(images)} page(s)")
                return images
            except Exception as e:
                logger.error(f"PDF conversion failed: {e}")
        # Fallback: try opening with PIL (won't work for multi-page but handles edge cases)
        try:
            img = Image.open(path)
            return [img]
        except Exception as e:
            logger.error(f"Fallback PIL open failed: {e}")
            return []
    else:
        try:
            img = Image.open(path).convert("RGB")
            return [img]
        except Exception as e:
            logger.error(f"Image open failed: {e}")
            return []


def preprocess_image(img: Image.Image) -> Image.Image:
    """Apply full preprocessing pipeline to a PIL image."""
    if CV2_AVAILABLE:
        arr = np.array(img.convert("RGB"))
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        bgr = _denoise(bgr)
        bgr = _deskew(bgr)
        bgr = _binarize(bgr)
        result = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    else:
        # Minimal preprocessing without OpenCV
        result = img.convert("L")  # grayscale
    return result


def _denoise(bgr: np.ndarray) -> np.ndarray:
    """Apply Non-Local Means denoising."""
    try:
        return cv2.fastNlMeansDenoisingColored(bgr, None, 10, 10, 7, 21)
    except Exception:
        return bgr


def _deskew(bgr: np.ndarray) -> np.ndarray:
    """Detect and correct skew angle."""
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:  # skip tiny corrections
            return bgr
        h, w = bgr.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(bgr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        logger.debug(f"Deskewed by {angle:.2f}°")
        return rotated
    except Exception as e:
        logger.debug(f"Deskew skipped: {e}")
        return bgr


def _binarize(bgr: np.ndarray) -> np.ndarray:
    """Adaptive thresholding for binarization."""
    try:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    except Exception:
        return bgr


def preprocess_document(file_path: Union[str, Path]) -> tuple[list[Image.Image], int]:
    """Full document preprocessing. Returns (pages, page_count)."""
    pages = load_document(file_path)
    processed = []
    for i, page in enumerate(pages):
        try:
            proc = preprocess_image(page)
            processed.append(proc)
        except Exception as e:
            logger.warning(f"Page {i+1} preprocessing failed: {e}; using original")
            processed.append(page)
    return processed, len(processed)

"""
Hybrid OCR engine: PaddleOCR primary, Tesseract fallback.
Returns extracted text with per-block confidence scores.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from PIL import Image
from loguru import logger

try:
    from paddleocr import PaddleOCR
    _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    PADDLE_AVAILABLE = True
    logger.info("PaddleOCR loaded")
except Exception as e:
    PADDLE_AVAILABLE = False
    _paddle_ocr = None
    logger.warning(f"PaddleOCR not available ({e}); Tesseract will be primary")

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
    logger.info("Tesseract available")
except Exception:
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract not available; OCR will be degraded")


@dataclass
class OCRBlock:
    text: str
    confidence: float
    bbox: Optional[list] = None  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]

@dataclass
class OCRResult:
    full_text: str
    blocks: list[OCRBlock] = field(default_factory=list)
    avg_confidence: float = 0.0
    engine_used: str = "none"


def run_ocr(image: Image.Image, confidence_threshold: float = 0.5) -> OCRResult:
    """Run hybrid OCR on a single PIL image."""
    result = None

    if PADDLE_AVAILABLE:
        result = _run_paddle(image, confidence_threshold)
        if result and result.avg_confidence >= confidence_threshold:
            return result
        logger.info("PaddleOCR confidence low; falling back to Tesseract")

    if TESSERACT_AVAILABLE:
        result = _run_tesseract(image)
        if result:
            return result

    # Last resort: return empty result with warning
    logger.error("No OCR engine available or all failed")
    return OCRResult(full_text="", blocks=[], avg_confidence=0.0, engine_used="none")


def _run_paddle(image: Image.Image, threshold: float) -> Optional[OCRResult]:
    try:
        import numpy as np
        arr = np.array(image.convert("RGB"))
        raw = _paddle_ocr.ocr(arr, cls=True)
        if not raw or not raw[0]:
            return None

        blocks = []
        for line in raw[0]:
            bbox, (text, conf) = line
            blocks.append(OCRBlock(text=text.strip(), confidence=float(conf), bbox=bbox))

        full_text = "\n".join(b.text for b in blocks)
        avg_conf = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        return OCRResult(full_text=full_text, blocks=blocks, avg_confidence=avg_conf, engine_used="paddleocr")
    except Exception as e:
        logger.warning(f"PaddleOCR error: {e}")
        return None


def _run_tesseract(image: Image.Image) -> Optional[OCRResult]:
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang="eng")
        blocks = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text:
                continue
            conf = float(data["conf"][i]) / 100.0
            if conf < 0:
                conf = 0.5  # Tesseract returns -1 for some tokens
            blocks.append(OCRBlock(text=text, confidence=conf))

        full_text = pytesseract.image_to_string(image, lang="eng")
        avg_conf = sum(b.confidence for b in blocks) / len(blocks) if blocks else 0.0
        return OCRResult(full_text=full_text.strip(), blocks=blocks, avg_confidence=avg_conf, engine_used="tesseract")
    except Exception as e:
        logger.warning(f"Tesseract error: {e}")
        return None


def run_ocr_on_document(pages: list[Image.Image], threshold: float = 0.5) -> OCRResult:
    """Run OCR across all pages, merging results."""
    all_blocks: list[OCRBlock] = []
    all_text_parts: list[str] = []

    for i, page in enumerate(pages):
        res = run_ocr(page, threshold)
        all_blocks.extend(res.blocks)
        all_text_parts.append(res.full_text)
        logger.debug(f"Page {i+1}: engine={res.engine_used}, confidence={res.avg_confidence:.2f}")

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(all_text_parts)
    avg_conf = sum(b.confidence for b in all_blocks) / len(all_blocks) if all_blocks else 0.0
    engine = "paddleocr" if PADDLE_AVAILABLE else ("tesseract" if TESSERACT_AVAILABLE else "none")
    return OCRResult(full_text=full_text, blocks=all_blocks, avg_confidence=avg_conf, engine_used=engine)

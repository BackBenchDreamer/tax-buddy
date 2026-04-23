"""
OCR Service — multi-page, confidence-scored extraction.

Engines (in priority order)
----------------------------
1. PaddleOCR v3  (if paddlepaddle is available)
2. Tesseract     (primary on macOS/Python 3.14 — no ARM64 paddlepaddle wheel)

Each text block carries:
  {text, bbox, confidence}

The service returns:
  {
    text:               str        (concatenated),
    blocks:             list[dict] (per-block detail),
    average_confidence: float,
  }
"""

import logging
from typing import Any, Dict, List

import cv2
import numpy as np
import pytesseract

from .preprocess import load_all_pages, to_grayscale, enhance_contrast, denoise
from app.core.config import settings

log = logging.getLogger(__name__)


class OCRService:
    """Multi-page OCR with PaddleOCR → Tesseract fallback."""

    def __init__(self):
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self.dpi = settings.OCR_DPI
        self.paddle_ocr = None

        try:
            from paddleocr import PaddleOCR
            self.paddle_ocr = PaddleOCR(
                lang="en",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            log.info("[OCR] PaddleOCR v3 initialised (threshold=%.2f)", self.confidence_threshold)
        except Exception as exc:
            log.warning("[OCR] PaddleOCR unavailable (%s) — Tesseract fallback active.", exc)

    # ------------------------------------------------------------------
    # PaddleOCR v3
    # ------------------------------------------------------------------
    def _run_paddle(self, image: np.ndarray) -> List[Dict[str, Any]]:
        if self.paddle_ocr is None:
            raise RuntimeError("PaddleOCR not initialised")
        results = self.paddle_ocr.predict(image)
        blocks: List[Dict[str, Any]] = []
        for page_result in results:
            try:
                texts  = page_result.get("rec_texts",  []) if hasattr(page_result, "get") else getattr(page_result, "rec_texts", [])
                scores = page_result.get("rec_scores", []) if hasattr(page_result, "get") else getattr(page_result, "rec_scores", [])
                boxes  = page_result.get("rec_boxes",  []) if hasattr(page_result, "get") else getattr(page_result, "rec_boxes", [])
            except Exception:
                texts, scores, boxes = [], [], []
            for text, score, box in zip(texts, scores, boxes):
                if not text or not text.strip():
                    continue
                flat = [float(c) for pt in box for c in (pt if hasattr(pt, "__iter__") else [pt])] if box is not None else []
                blocks.append({"text": text.strip(), "bbox": flat, "confidence": round(float(score), 4)})
        return blocks

    # ------------------------------------------------------------------
    # Tesseract
    # ------------------------------------------------------------------
    def _run_tesseract(self, image: np.ndarray) -> List[Dict[str, Any]]:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB) if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        custom_config = "--oem 3 --psm 6"
        data = pytesseract.image_to_data(rgb, config=custom_config, output_type=pytesseract.Output.DICT)
        blocks: List[Dict[str, Any]] = []
        for i in range(len(data["text"])):
            txt = data["text"][i].strip()
            if not txt:
                continue
            conf = max(0.0, float(data["conf"][i]) / 100.0)
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            blocks.append({"text": txt, "bbox": [x, y, x + w, y + h], "confidence": round(conf, 4)})
        return blocks

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        text = " ".join(b["text"] for b in blocks)
        avg_conf = round(float(np.mean([b["confidence"] for b in blocks])), 4) if blocks else 0.0
        return {"text": text, "blocks": blocks, "average_confidence": avg_conf}

    # ------------------------------------------------------------------
    # Public entry point — all pages
    # ------------------------------------------------------------------
    def extract(self, input_path: str) -> Dict[str, Any]:
        """Run OCR on every page; return concatenated text + per-block confidence."""
        log.info("[OCR] Starting extraction: %s", input_path)
        all_blocks: List[Dict[str, Any]] = []

        try:
            pages = load_all_pages(input_path, dpi=self.dpi)
        except Exception as exc:
            log.error("[OCR] Failed to load pages: %s", exc)
            raise

        log.info("[OCR] %d page(s) loaded", len(pages))

        for idx, page_bgr in enumerate(pages):
            page_num = idx + 1
            gray     = to_grayscale(page_bgr)
            enhanced = enhance_contrast(gray)
            denoised = denoise(enhanced)

            # PaddleOCR attempt
            if self.paddle_ocr is not None:
                try:
                    paddle_blocks = self._run_paddle(denoised)
                    avg = float(np.mean([b["confidence"] for b in paddle_blocks])) if paddle_blocks else 0.0
                    if avg >= self.confidence_threshold:
                        log.info("[OCR] Page %d: PaddleOCR OK (blocks=%d, avg_conf=%.3f)", page_num, len(paddle_blocks), avg)
                        all_blocks.extend(paddle_blocks)
                        continue
                    log.warning("[OCR] Page %d: PaddleOCR low conf (%.3f) — using Tesseract", page_num, avg)
                except Exception as exc:
                    log.warning("[OCR] Page %d: PaddleOCR error (%s) — using Tesseract", page_num, exc)

            # Tesseract
            try:
                tess_blocks = self._run_tesseract(denoised)
                log.info("[OCR] Page %d: Tesseract OK (blocks=%d)", page_num, len(tess_blocks))
                all_blocks.extend(tess_blocks)
            except Exception as exc:
                log.error("[OCR] Page %d: Both engines failed — skipping (%s)", page_num, exc)

        if not all_blocks:
            raise RuntimeError(f"OCR produced no output for: {input_path}")

        result = self._aggregate(all_blocks)
        log.info(
            "[OCR] Done — %d blocks, %d chars, avg_conf=%.3f",
            len(all_blocks), len(result["text"]), result["average_confidence"],
        )
        return result

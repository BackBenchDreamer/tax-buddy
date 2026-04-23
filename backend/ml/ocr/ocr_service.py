"""
OCR Service — processes ALL pages of a PDF, not just page 1.

Root-cause fix: Tesseract was only called on the first page.
This version converts all pages and concatenates the full text.
"""

import logging
from typing import Any, Dict, List

import cv2
import numpy as np
import pytesseract

from .preprocess import load_all_pages, to_grayscale, denoise

log = logging.getLogger(__name__)


class OCRService:
    """High-level OCR service.

    Primary engine : PaddleOCR v3  (lazy, skipped if paddlepaddle unavailable)
    Fallback engine: Tesseract     (processes ALL pages)
    """

    def __init__(
        self,
        lang: str = "en",
        confidence_threshold: float = 0.70,
    ):
        self.confidence_threshold = confidence_threshold
        self.paddle_ocr = None  # lazy-initialised

        try:
            from paddleocr import PaddleOCR
            self.paddle_ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            log.info("PaddleOCR initialised — lang=%s", lang)
        except Exception as exc:
            log.warning(
                "PaddleOCR unavailable (%s) — Tesseract fallback active.", exc
            )

    # ------------------------------------------------------------------
    # PaddleOCR v3 runner (single image)
    # ------------------------------------------------------------------
    def _run_paddle_image(self, image: np.ndarray) -> List[Dict[str, Any]]:
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
                blocks.append({"text": text.strip(), "bbox": flat, "confidence": float(score)})
        return blocks

    # ------------------------------------------------------------------
    # Tesseract runner (single image)
    # ------------------------------------------------------------------
    def _run_tesseract_image(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Run Tesseract on a single preprocessed image."""
        # Use image_to_string for clean text extraction
        if len(image.shape) == 2:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Use page segmentation mode 1 (auto with OSD) for better layout
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(rgb, config=custom_config)

        # Also get word-level data for bboxes/confidence
        data = pytesseract.image_to_data(rgb, config=custom_config, output_type=pytesseract.Output.DICT)
        blocks: List[Dict[str, Any]] = []
        n = len(data["text"])
        for i in range(n):
            txt = data["text"][i].strip()
            if not txt:
                continue
            conf_raw = data["conf"][i]
            conf = max(0.0, float(conf_raw) / 100.0)
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            blocks.append({"text": txt, "bbox": [x, y, x + w, y + h], "confidence": conf})
        return blocks

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        text = " ".join(b["text"] for b in blocks)
        avg_conf = float(np.mean([b["confidence"] for b in blocks])) if blocks else 0.0
        return {"text": text, "blocks": blocks, "average_confidence": avg_conf}

    # ------------------------------------------------------------------
    # Public entry point — processes ALL pages
    # ------------------------------------------------------------------
    def extract(self, input_path: str) -> Dict[str, Any]:
        """Run OCR on every page and return concatenated structured output.

        For multi-page PDFs this ensures no financial data is missed.
        """
        log.info("[OCR] Extracting from: %s", input_path)
        all_blocks: List[Dict[str, Any]] = []

        # Load all pages as numpy arrays
        try:
            pages = load_all_pages(input_path)
        except Exception as exc:
            log.exception("Failed to load pages from %s", input_path)
            raise exc

        log.info("[OCR] %d page(s) loaded — running Tesseract on each", len(pages))

        for page_idx, page_img in enumerate(pages):
            gray = to_grayscale(page_img)
            denoised = denoise(gray)  # light denoise only — skip threshold/deskew for text PDFs

            # Try PaddleOCR first
            if self.paddle_ocr is not None:
                try:
                    paddle_blocks = self._run_paddle_image(denoised)
                    avg = float(np.mean([b["confidence"] for b in paddle_blocks])) if paddle_blocks else 0.0
                    if avg >= self.confidence_threshold:
                        log.info("[OCR] Page %d: PaddleOCR OK (avg_conf=%.2f, blocks=%d)", page_idx + 1, avg, len(paddle_blocks))
                        all_blocks.extend(paddle_blocks)
                        continue
                    log.info("[OCR] Page %d: PaddleOCR low conf (%.2f) — using Tesseract", page_idx + 1, avg)
                except Exception as exc:
                    log.warning("[OCR] Page %d: PaddleOCR failed (%s) — using Tesseract", page_idx + 1, exc)

            # Tesseract fallback
            try:
                tess_blocks = self._run_tesseract_image(denoised)
                log.info("[OCR] Page %d: Tesseract OK (%d blocks)", page_idx + 1, len(tess_blocks))
                all_blocks.extend(tess_blocks)
            except Exception as exc:
                log.exception("[OCR] Page %d: Tesseract also failed — skipping page", page_idx + 1)

        if not all_blocks:
            raise RuntimeError(f"OCR produced no output for {input_path}")

        result = self._aggregate(all_blocks)
        log.info(
            "[OCR] Done — %d total blocks, %d chars, avg_conf=%.3f",
            len(all_blocks), len(result["text"]), result["average_confidence"],
        )
        return result

"""
OCR Service — multi-page, confidence-scored extraction.

Engines (in strict priority order)
-----------------------------------
1. Direct PDF text extraction (pdfplumber/PyMuPDF) — if clean text exists, skip OCR
2. PaddleOCR — primary OCR engine for image-based/scanned pages
3. Tesseract — fallback ONLY if PaddleOCR fails or returns low confidence

Each text block carries:
  {text, bbox, confidence}

The service returns:
  {
    text:               str        (concatenated),
    blocks:             list[dict] (per-block detail),
    average_confidence: float,
    extraction_method:  str        (which engine was used)
  }
"""

import logging
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import pytesseract

from .preprocess import load_all_pages, to_grayscale, enhance_contrast, denoise
from app.core.config import settings

# PDF text extraction libraries
try:
    import pdfplumber  # type: ignore
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None  # type: ignore
    PDFPLUMBER_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    from fitz import Page  # type: ignore[attr-defined]
    PYMUPDF_AVAILABLE = True
except ImportError:
    fitz = None  # type: ignore
    PYMUPDF_AVAILABLE = False
    Page = None  # type: ignore

log = logging.getLogger(__name__)


class OCRService:
    """Multi-page OCR with strict priority: PDF text → PaddleOCR → Tesseract."""

    def __init__(self):
        self.confidence_threshold = settings.OCR_CONFIDENCE_THRESHOLD
        self.dpi = settings.OCR_DPI
        self.paddle_ocr = None

        try:
            from paddleocr import PaddleOCR
            self.paddle_ocr = PaddleOCR(
                lang="en",
                use_angle_cls=True,  # Enable angle classification as per requirements
            )
            log.info("[OCR] PaddleOCR initialised (threshold=%.2f, use_angle_cls=True)", self.confidence_threshold)
        except Exception as exc:
            log.warning("[OCR] PaddleOCR unavailable (%s) — will use Tesseract fallback.", exc)

    # ------------------------------------------------------------------
    # Direct PDF text extraction (Priority 1)
    # ------------------------------------------------------------------
    def _extract_pdf_text_pdfplumber(self, pdf_path: str) -> Optional[str]:
        """Extract text directly from PDF using pdfplumber."""
        if not PDFPLUMBER_AVAILABLE:
            return None
        try:
            if pdfplumber is None:
                return None
            with pdfplumber.open(pdf_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                
                if text_parts:
                    full_text = "\n".join(text_parts)
                    # Check if text is meaningful (not just whitespace/garbage)
                    if len(full_text.strip()) > 50:  # Minimum threshold
                        log.info("[OCR] pdfplumber extracted %d chars from %d pages", len(full_text), len(pdf.pages))
                        return full_text
            return None
        except Exception as exc:
            log.debug("[OCR] pdfplumber extraction failed: %s", exc)
            return None

    def _extract_pdf_text_pymupdf(self, pdf_path: str) -> Optional[str]:
        """Extract text directly from PDF using PyMuPDF."""
        if not PYMUPDF_AVAILABLE:
            return None
        try:
            if fitz is None:
                return None
            doc = fitz.open(pdf_path)
            text_parts = []
            for page in doc:
                page_text = page.get_text()  # type: ignore[attr-defined]
                if page_text:
                    text_parts.append(page_text)
            doc.close()
            
            if text_parts:
                full_text = "\n".join(text_parts)
                if len(full_text.strip()) > 50:
                    log.info("[OCR] PyMuPDF extracted %d chars from %d pages", len(full_text), len(text_parts))
                    return full_text
            return None
        except Exception as exc:
            log.debug("[OCR] PyMuPDF extraction failed: %s", exc)
            return None

    def _try_direct_pdf_extraction(self, pdf_path: str) -> Optional[str]:
        """Try direct PDF text extraction before OCR."""
        if not pdf_path.lower().endswith('.pdf'):
            return None
        
        # Try pdfplumber first (generally better for forms)
        text = self._extract_pdf_text_pdfplumber(pdf_path)
        if text:
            log.info("[OCR] ✓ Direct PDF extraction successful (pdfplumber)")
            return text
        
        # Fallback to PyMuPDF
        text = self._extract_pdf_text_pymupdf(pdf_path)
        if text:
            log.info("[OCR] ✓ Direct PDF extraction successful (PyMuPDF)")
            return text
        
        log.info("[OCR] Direct PDF extraction yielded no usable text — proceeding to OCR")
        return None

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
    # Tesseract (Priority 3 - Fallback only)
    # ------------------------------------------------------------------
    def _run_tesseract(self, image: np.ndarray) -> List[Dict[str, Any]]:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB) if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        custom_config = "--oem 1 --psm 6"  # OEM 1 as per requirements
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
    # Aggregate — line-based grouping for structure-aware extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group blocks into lines using Y-coordinate proximity, then join.

        This produces structured text with newlines between logical lines,
        which is critical for keyword-based extraction that relies on
        same-line matching (e.g., "Gross Salary  751585.00").
        """
        if not blocks:
            return {"text": "", "blocks": [], "average_confidence": 0.0}

        avg_conf = round(float(np.mean([b["confidence"] for b in blocks])), 4)

        # Sort blocks by vertical position (top of bbox), then horizontal
        def _y_center(b: Dict[str, Any]) -> float:
            bbox = b.get("bbox", [])
            if len(bbox) >= 4:
                return (bbox[1] + bbox[3]) / 2.0  # (top + bottom) / 2
            return 0.0

        def _x_start(b: Dict[str, Any]) -> float:
            bbox = b.get("bbox", [])
            return float(bbox[0]) if bbox else 0.0

        sorted_blocks = sorted(blocks, key=lambda b: (_y_center(b), _x_start(b)))

        # Group into lines — blocks within 15px vertically are same line
        lines: List[List[Dict[str, Any]]] = []
        current_line: List[Dict[str, Any]] = []
        prev_y = -999.0
        LINE_THRESHOLD = 15.0

        for block in sorted_blocks:
            y = _y_center(block)
            if current_line and abs(y - prev_y) > LINE_THRESHOLD:
                lines.append(current_line)
                current_line = []
            current_line.append(block)
            prev_y = y

        if current_line:
            lines.append(current_line)

        # Join blocks within each line with spaces, lines with newlines
        text_lines = []
        for line_blocks in lines:
            line_text = " ".join(b["text"] for b in line_blocks)
            text_lines.append(line_text)

        text = "\n".join(text_lines)

        log.info("[OCR] Aggregated %d blocks → %d lines", len(blocks), len(lines))

        return {"text": text, "blocks": blocks, "average_confidence": avg_conf}

    # ------------------------------------------------------------------
    # Public entry point — all pages with strict priority order
    # ------------------------------------------------------------------
    def extract(self, input_path: str, max_pages: int = 2) -> Dict[str, Any]:
        """
        Extract text using strict priority order:
        1. Direct PDF text extraction (if PDF and text exists)
        2. PaddleOCR (primary OCR engine)
        3. Tesseract (fallback only)

        Args:
            input_path: Path to PDF or image
            max_pages: Maximum pages to process (default 2 for performance)

        Returns:
            {
                text: str,
                blocks: list[dict],
                average_confidence: float,
                extraction_method: str
            }
        """
        log.info("[OCR] Starting extraction: %s (max_pages=%d)", input_path, max_pages)
        
        # PRIORITY 1: Try direct PDF text extraction first
        if input_path.lower().endswith('.pdf'):
            direct_text = self._try_direct_pdf_extraction(input_path)
            if direct_text:
                # Create synthetic blocks for direct extraction (confidence = 1.0)
                blocks = [{
                    "text": direct_text,
                    "bbox": [],
                    "confidence": 1.0
                }]
                return {
                    "text": direct_text,
                    "blocks": blocks,
                    "average_confidence": 1.0,
                    "extraction_method": "direct_pdf"
                }
        
        # PRIORITY 2 & 3: OCR pipeline (PaddleOCR → Tesseract)
        all_blocks: List[Dict[str, Any]] = []
        extraction_methods = []

        try:
            pages = load_all_pages(input_path, dpi=self.dpi)
        except Exception as exc:
            log.error("[OCR] Failed to load pages: %s", exc)
            raise

        # PERFORMANCE: Limit page processing to first N pages
        if len(pages) > max_pages:
            log.warning("[OCR] Document has %d pages, limiting to first %d for performance", len(pages), max_pages)
            pages = pages[:max_pages]

        log.info("[OCR] %d page(s) to process via OCR", len(pages))

        for idx, page_bgr in enumerate(pages):
            page_num = idx + 1
            gray     = to_grayscale(page_bgr)
            enhanced = enhance_contrast(gray)
            denoised = denoise(enhanced)

            page_method = None

            # PRIORITY 2: Try PaddleOCR first
            if self.paddle_ocr is not None:
                try:
                    paddle_blocks = self._run_paddle(denoised)
                    avg = float(np.mean([b["confidence"] for b in paddle_blocks])) if paddle_blocks else 0.0
                    
                    if paddle_blocks and avg >= self.confidence_threshold:
                        log.info("[OCR] Page %d: ✓ PaddleOCR (blocks=%d, avg_conf=%.3f)", page_num, len(paddle_blocks), avg)
                        all_blocks.extend(paddle_blocks)
                        page_method = "paddleocr"
                        extraction_methods.append(page_method)
                        continue
                    else:
                        log.warning("[OCR] Page %d: PaddleOCR low confidence (%.3f < %.3f) — falling back to Tesseract",
                                  page_num, avg, self.confidence_threshold)
                except Exception as exc:
                    log.warning("[OCR] Page %d: PaddleOCR error (%s) — falling back to Tesseract", page_num, exc)
            else:
                log.debug("[OCR] Page %d: PaddleOCR not available — using Tesseract", page_num)

            # PRIORITY 3: Tesseract fallback
            try:
                tess_blocks = self._run_tesseract(denoised)
                log.info("[OCR] Page %d: ✓ Tesseract fallback (blocks=%d)", page_num, len(tess_blocks))
                all_blocks.extend(tess_blocks)
                page_method = "tesseract"
                extraction_methods.append(page_method)
            except Exception as exc:
                log.error("[OCR] Page %d: ✗ Both OCR engines failed — skipping (%s)", page_num, exc)

        if not all_blocks:
            raise RuntimeError(f"OCR produced no output for: {input_path}")

        result = self._aggregate(all_blocks)
        
        # Determine overall extraction method
        if extraction_methods:
            primary_method = max(set(extraction_methods), key=extraction_methods.count)
            result["extraction_method"] = primary_method
        else:
            result["extraction_method"] = "unknown"
        
        log.info(
            "[OCR] ✓ Extraction complete — %d blocks, %d chars, avg_conf=%.3f, method=%s",
            len(all_blocks), len(result["text"]), result["average_confidence"], result["extraction_method"]
        )
        return result

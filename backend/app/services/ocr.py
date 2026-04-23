from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.services.preprocessing import PreprocessResult


@dataclass
class OCRResult:
    text: str
    confidence: float
    lines: list[str]
    engine: str
    warnings: list[str]


class HybridOCRService:
    def extract_text(self, file_path: Path, preprocessed: PreprocessResult) -> OCRResult:
        warnings: list[str] = []
        if file_path.suffix.lower() == ".pdf":
            text = self._pdf_text(file_path)
            if text.strip():
                return OCRResult(text=text, confidence=0.88, lines=text.splitlines(), engine="pdf_text", warnings=[])
            warnings.append("pdf_text_extraction_fell_back_to_ocr")

        image_bytes = preprocessed.image_bytes
        if image_bytes is not None:
            paddle_text = self._run_paddle_ocr(image_bytes)
            if paddle_text.text.strip():
                return paddle_text
            warnings.extend(paddle_text.warnings or ["paddleocr_empty_result"])

            tesseract_text = self._run_tesseract_ocr(image_bytes)
            if tesseract_text.text.strip():
                return tesseract_text
            warnings.extend(tesseract_text.warnings or ["tesseract_empty_result"])

        return OCRResult(text="", confidence=0.0, lines=[], engine="none", warnings=warnings or ["no_ocr_available"])

    def _pdf_text(self, file_path: Path) -> str:
        try:
            import pdfplumber

            texts: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    texts.append(page.extract_text() or "")
            return "\n".join(texts)
        except Exception:
            return ""

    def _run_paddle_ocr(self, image_bytes: bytes) -> OCRResult:
        warnings: list[str] = []
        try:
            from io import BytesIO

            from PIL import Image

            from paddleocr import PaddleOCR

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            result = ocr.ocr(np.array(image), cls=True)
            lines: list[str] = []
            confidences: list[float] = []
            for page in result or []:
                for item in page or []:
                    if not item:
                        continue
                    text = item[1][0]
                    score = float(item[1][1])
                    if text:
                        lines.append(text)
                        confidences.append(score)
            text = "\n".join(lines)
            confidence = float(sum(confidences) / max(len(confidences), 1)) if confidences else 0.0
            return OCRResult(text=text, confidence=confidence, lines=lines, engine="paddleocr", warnings=warnings)
        except Exception as exc:
            warnings.append(f"paddleocr_failed:{exc.__class__.__name__}")
            return OCRResult(text="", confidence=0.0, lines=[], engine="paddleocr", warnings=warnings)

    def _run_tesseract_ocr(self, image_bytes: bytes) -> OCRResult:
        warnings: list[str] = []
        try:
            from io import BytesIO

            import pytesseract
            from PIL import Image

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            text = pytesseract.image_to_string(image)
            confidence = 0.72 if text.strip() else 0.0
            return OCRResult(text=text, confidence=confidence, lines=[line for line in text.splitlines() if line.strip()], engine="tesseract", warnings=warnings)
        except Exception as exc:
            warnings.append(f"tesseract_failed:{exc.__class__.__name__}")
            return OCRResult(text="", confidence=0.0, lines=[], engine="tesseract", warnings=warnings)

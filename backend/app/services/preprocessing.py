from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


@dataclass
class PreprocessResult:
    image_bytes: bytes | None
    page_count: int
    notes: list[str]


class DocumentPreprocessor:
    def preprocess(self, file_path: Path) -> PreprocessResult:
        suffix = file_path.suffix.lower()
        notes: list[str] = []
        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            image = Image.open(file_path).convert("RGB")
            processed = self._clean_image(image)
            output = io.BytesIO()
            processed.save(output, format="PNG")
            return PreprocessResult(image_bytes=output.getvalue(), page_count=1, notes=["image_preprocessed"])

        if suffix == ".pdf":
            notes.append("pdf_detected")
            return PreprocessResult(image_bytes=None, page_count=self._count_pdf_pages(file_path), notes=notes)

        notes.append("unsupported_format_pass_through")
        return PreprocessResult(image_bytes=None, page_count=1, notes=notes)

    def _clean_image(self, image: Image.Image) -> Image.Image:
        rgb = np.array(image)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=15)
        blurred = cv2.GaussianBlur(denoised, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        corrected = self._deskew(thresh)
        return Image.fromarray(corrected)

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(image < 255))
        if len(coords) == 0:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (height, width) = image.shape[:2]
        matrix = cv2.getRotationMatrix2D((width // 2, height // 2), angle, 1.0)
        return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def _count_pdf_pages(self, file_path: Path) -> int:
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                return len(pdf.pages)
        except Exception:
            return 1

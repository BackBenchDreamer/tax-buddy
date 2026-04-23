from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from app.ml.infer import HybridNerExtractor
from app.schemas import EntitySpan, ExtractionResult
from app.services.normalization import TextNormalizer
from app.services.ocr import HybridOCRService
from app.services.preprocessing import DocumentPreprocessor


@dataclass
class ExtractionArtifact:
    extraction: ExtractionResult
    ocr_engine: str
    ocr_warnings: list[str]


class ExtractionService:
    def __init__(self, model_path: Path | None = None):
        self.preprocessor = DocumentPreprocessor()
        self.ocr = HybridOCRService()
        self.normalizer = TextNormalizer()
        self.ner = HybridNerExtractor(model_path=model_path)

    def extract(self, document_id: int, file_path: Path) -> ExtractionArtifact:
        preprocessed = self.preprocessor.preprocess(file_path)
        ocr_result = self.ocr.extract_text(file_path, preprocessed)
        normalized = self.normalizer.normalize(ocr_result.text, source=ocr_result.engine)
        ml_result = self.ner.extract(normalized.text)
        heuristics = self._heuristic_entities(normalized.text)
        entities = self._merge_entities(ml_result.entities + heuristics)
        confidence = self._aggregate_confidence(ocr_result.confidence, ml_result.confidence, entities)
        extraction = ExtractionResult(
            document_id=document_id,
            text=ocr_result.text,
            normalized_text=normalized.text,
            confidence=confidence,
            entities=entities,
            layout_metadata={
                **normalized.layout_metadata,
                "ocr_engine": ocr_result.engine,
                "ocr_warnings": ocr_result.warnings,
                "preprocess_notes": preprocessed.notes,
            },
        )
        return ExtractionArtifact(extraction=extraction, ocr_engine=ocr_result.engine, ocr_warnings=ocr_result.warnings)

    def _heuristic_entities(self, text: str) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        lines = text.splitlines()
        for index, line in enumerate(lines):
            upper = line.upper()
            if "EMPLOYER" in upper and ":" in line:
                entities.append(EntitySpan(label="EmployerName", value=line.split(":", 1)[1].strip(), confidence=0.84, source="heuristic", page=index + 1))
            if "EMPLOYEE" in upper and ":" in line:
                entities.append(EntitySpan(label="EmployeeName", value=line.split(":", 1)[1].strip(), confidence=0.84, source="heuristic", page=index + 1))
            if "GROSS SALARY" in upper:
                amount = self._extract_amount(line)
                if amount is not None:
                    entities.append(EntitySpan(label="GrossIncome", value=f"{amount:.2f}", confidence=0.86, source="heuristic", page=index + 1))
            if "STANDARD DEDUCTION" in upper:
                amount = self._extract_amount(line)
                if amount is not None:
                    entities.append(EntitySpan(label="StandardDeduction", value=f"{amount:.2f}", confidence=0.86, source="heuristic", page=index + 1))
            if "80C" in upper:
                amount = self._extract_amount(line)
                if amount is not None:
                    entities.append(EntitySpan(label="Section80C", value=f"{amount:.2f}", confidence=0.88, source="heuristic", page=index + 1))
            if "80D" in upper:
                amount = self._extract_amount(line)
                if amount is not None:
                    entities.append(EntitySpan(label="Section80D", value=f"{amount:.2f}", confidence=0.88, source="heuristic", page=index + 1))
            if "TDS" in upper:
                amount = self._extract_amount(line)
                if amount is not None:
                    entities.append(EntitySpan(label="TDS", value=f"{amount:.2f}", confidence=0.9, source="heuristic", page=index + 1))
        return entities

    def _extract_amount(self, text: str) -> float | None:
        match = re.search(r"(?:Rs\.?|INR)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", text.replace(" ", ""), flags=re.IGNORECASE)
        if not match:
            match = re.search(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", text)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))

    def _merge_entities(self, entities: list[EntitySpan]) -> list[EntitySpan]:
        merged: dict[tuple[str, str], EntitySpan] = {}
        for entity in entities:
            key = (entity.label, entity.value.strip().upper())
            existing = merged.get(key)
            if existing is None or entity.confidence > existing.confidence:
                merged[key] = entity
        return sorted(merged.values(), key=lambda item: (-item.confidence, item.label, item.value))

    def _aggregate_confidence(self, ocr_confidence: float, ner_confidence: float, entities: list[EntitySpan]) -> float:
        entity_boost = min(len(entities) / 15.0, 1.0) * 0.1
        confidence = 0.5 * ocr_confidence + 0.4 * ner_confidence + entity_boost
        return max(0.0, min(confidence, 1.0))

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from app.ml.schema import FIELD_PATTERNS, ENTITY_LABELS
from app.schemas import EntitySpan


@dataclass
class InferenceOutput:
    entities: list[EntitySpan]
    confidence: float
    model_used: str


class HybridNerExtractor:
    def __init__(self, model_path: Path | None = None):
        self.model_path = model_path
        self._pipeline = None

    def _load_pipeline(self) -> Any | None:
        if self._pipeline is not None:
            return self._pipeline
        if self.model_path is None or not self.model_path.exists():
            return None
        try:
            from transformers import pipeline

            self._pipeline = pipeline("token-classification", model=str(self.model_path), aggregation_strategy="simple")
        except Exception:
            self._pipeline = None
        return self._pipeline

    def extract(self, text: str) -> InferenceOutput:
        entities = self._regex_entities(text)
        confidence_scores = [entity.confidence for entity in entities]
        pipeline = self._load_pipeline()
        model_used = "regex"
        if pipeline is not None:
            try:
                predictions = pipeline(text)
                for prediction in predictions:
                    label = str(prediction.get("entity_group") or prediction.get("entity") or "")
                    value = str(prediction.get("word") or prediction.get("token") or "").replace("##", "")
                    score = float(prediction.get("score") or 0.0)
                    if label in ENTITY_LABELS and value:
                        entities.append(EntitySpan(label=label, value=value, confidence=score, source="transformer"))
                        confidence_scores.append(score)
                model_used = "transformer+regex"
            except Exception:
                model_used = "regex"
        deduplicated = self._deduplicate(entities)
        confidence = sum(confidence_scores) / max(len(confidence_scores), 1)
        return InferenceOutput(entities=deduplicated, confidence=min(max(confidence, 0.0), 1.0), model_used=model_used)

    def _regex_entities(self, text: str) -> list[EntitySpan]:
        entities: list[EntitySpan] = []
        upper_text = text.upper()
        for label, pattern in FIELD_PATTERNS.items():
            for match in re.finditer(pattern, upper_text, flags=re.IGNORECASE):
                value = match.group(1) if match.groups() else match.group(0)
                entities.append(EntitySpan(label=label, value=value.strip(), confidence=0.98, source="regex"))
        pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", upper_text)
        if pan_match:
            entities.append(EntitySpan(label="PAN", value=pan_match.group(0), confidence=0.99, source="regex"))
        tan_match = re.search(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b", upper_text)
        if tan_match:
            entities.append(EntitySpan(label="TAN", value=tan_match.group(0), confidence=0.99, source="regex"))
        return entities

    def _deduplicate(self, entities: list[EntitySpan]) -> list[EntitySpan]:
        seen: set[tuple[str, str]] = set()
        deduplicated: list[EntitySpan] = []
        for entity in sorted(entities, key=lambda item: item.confidence, reverse=True):
            key = (entity.label, entity.value.upper())
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(entity)
        return deduplicated

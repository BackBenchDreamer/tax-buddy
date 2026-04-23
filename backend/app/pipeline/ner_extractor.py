"""
Hybrid NER extractor: transformer-based NER (XLM-RoBERTa) + regex + heuristics.
Extracts tax-relevant entities from OCR text.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional, Any
from loguru import logger

# Regex patterns for critical Indian tax fields
PATTERNS = {
    "pan": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "tan": re.compile(r"\b[A-Z]{4}[0-9]{5}[A-Z]\b"),
    "assessment_year": re.compile(r"\b(20\d{2}[-–]\d{2,4})\b"),
    "amount": re.compile(r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)"),
    "amount_bare": re.compile(r"\b(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?)\b"),
}

# Section keywords -> normalized field names
SECTION_KEYWORDS = {
    "section 80c": "section_80c",
    "80c": "section_80c",
    "section 80d": "section_80d",
    "80d": "section_80d",
    "section 80e": "section_80e",
    "80e": "section_80e",
    "section 80g": "section_80g",
    "80g": "section_80g",
    "standard deduction": "standard_deduction",
    "tds": "tds_deducted",
    "tax deducted at source": "tds_deducted",
    "gross salary": "gross_salary",
    "basic salary": "basic_salary",
    "hra": "hra",
    "house rent allowance": "hra",
    "special allowance": "special_allowance",
    "net taxable income": "net_taxable_income",
    "taxable income": "net_taxable_income",
    "employer name": "employer_name",
    "name of employer": "employer_name",
    "employee name": "employee_name",
    "name of employee": "employee_name",
}


@dataclass
class ExtractedEntity:
    value: Any
    confidence: float
    source: str  # "ner" | "regex" | "heuristic"


@dataclass
class ExtractionOutput:
    entities: dict[str, ExtractedEntity] = field(default_factory=dict)
    avg_ner_confidence: float = 0.0


class HybridNERExtractor:
    def __init__(self, model_path: str = "", model_name: str = "xlm-roberta-base"):
        self.model_path = model_path
        self.model_name = model_name
        self._pipeline = None
        self._load_model()

    def _load_model(self):
        if not self.model_path:
            logger.info("No fine-tuned NER model path; using regex+heuristics only")
            return
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "token-classification",
                model=self.model_path,
                aggregation_strategy="simple",
            )
            logger.info(f"NER model loaded from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load NER model: {e}; falling back to regex")

    def extract(self, text: str) -> ExtractionOutput:
        output = ExtractionOutput()
        regex_entities = self._regex_extract(text)
        for k, v in regex_entities.items():
            output.entities[k] = v

        if self._pipeline:
            ner_entities, avg_conf = self._ner_extract(text)
            for k, v in ner_entities.items():
                if k not in output.entities or output.entities[k].confidence < v.confidence:
                    output.entities[k] = v
            output.avg_ner_confidence = avg_conf
        else:
            output.avg_ner_confidence = 0.7  # assume reasonable for regex

        heuristic_entities = self._heuristic_extract(text)
        for k, v in heuristic_entities.items():
            if k not in output.entities:
                output.entities[k] = v

        return output

    def _regex_extract(self, text: str) -> dict[str, ExtractedEntity]:
        entities = {}
        # PAN
        pan_match = PATTERNS["pan"].search(text)
        if pan_match:
            entities["pan"] = ExtractedEntity(value=pan_match.group(), confidence=0.99, source="regex")

        # TAN
        tan_match = PATTERNS["tan"].search(text)
        if tan_match:
            entities["tan"] = ExtractedEntity(value=tan_match.group(), confidence=0.99, source="regex")

        # Assessment Year
        ay_match = PATTERNS["assessment_year"].search(text)
        if ay_match:
            entities["assessment_year"] = ExtractedEntity(value=ay_match.group(), confidence=0.95, source="regex")

        return entities

    def _heuristic_extract(self, text: str) -> dict[str, ExtractedEntity]:
        """Line-by-line keyword + amount heuristics."""
        entities = {}
        lines = text.splitlines()

        for line in lines:
            line_lower = line.lower().strip()
            for keyword, field_name in SECTION_KEYWORDS.items():
                if keyword in line_lower and field_name not in entities:
                    amount = self._extract_amount_from_line(line)
                    if amount is not None:
                        entities[field_name] = ExtractedEntity(value=amount, confidence=0.75, source="heuristic")
                    elif field_name in ("employee_name", "employer_name"):
                        # Try to extract name after the keyword
                        idx = line_lower.find(keyword)
                        rest = line[idx + len(keyword):].strip(" :–-")
                        if rest:
                            entities[field_name] = ExtractedEntity(value=rest[:100], confidence=0.65, source="heuristic")

        return entities

    def _extract_amount_from_line(self, line: str) -> Optional[float]:
        m = PATTERNS["amount"].search(line)
        if m:
            return _parse_amount(m.group(1))
        m = PATTERNS["amount_bare"].search(line)
        if m:
            return _parse_amount(m.group(1))
        return None

    def _ner_extract(self, text: str) -> tuple[dict[str, ExtractedEntity], float]:
        entities = {}
        confidences = []
        try:
            # Chunk text to avoid token limit
            chunk_size = 400
            words = text.split()
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                results = self._pipeline(chunk)
                for res in results:
                    label = res["entity_group"].lower()
                    value = res["word"]
                    score = float(res["score"])
                    confidences.append(score)
                    mapped = _map_ner_label(label)
                    if mapped and (mapped not in entities or entities[mapped].confidence < score):
                        entities[mapped] = ExtractedEntity(value=value, confidence=score, source="ner")
        except Exception as e:
            logger.warning(f"NER inference error: {e}")

        avg = sum(confidences) / len(confidences) if confidences else 0.0
        return entities, avg


def _parse_amount(s: str) -> float:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return 0.0


def _map_ner_label(label: str) -> Optional[str]:
    mapping = {
        "pan": "pan",
        "tan": "tan",
        "per": "employee_name",
        "org": "employer_name",
        "salary": "gross_salary",
        "tds": "tds_deducted",
        "deduction": "section_80c",
    }
    return mapping.get(label)

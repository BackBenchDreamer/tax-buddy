from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class TokenSample:
    tokens: list[str]
    ner_tags: list[str]


@dataclass
class SpanSample:
    text: str
    entities: list[dict[str, object]]


class DatasetLoader:
    def load_token_classification(self, path: Path) -> list[TokenSample]:
        samples: list[TokenSample] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                samples.append(TokenSample(tokens=payload["tokens"], ner_tags=payload["ner_tags"]))
        return samples

    def load_span_annotations(self, path: Path) -> list[SpanSample]:
        samples: list[SpanSample] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                samples.append(SpanSample(text=payload["text"], entities=payload["entities"]))
        return samples

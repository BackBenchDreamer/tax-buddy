from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class NormalizedDocument:
    text: str
    tokens: list[str]
    layout_metadata: dict[str, list[dict[str, float | int | str]]] = field(default_factory=dict)


class TextNormalizer:
    def normalize(self, text: str, source: str = "ocr") -> NormalizedDocument:
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[\u00A0\t]+", " ", cleaned)
        cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
        tokens = re.findall(r"[A-Z0-9/\-.]+|[A-Za-z]+|\d+(?:,\d{3})*(?:\.\d+)?", cleaned.upper())
        layout = {
            "source": source,
            "lines": [{"index": idx, "text": line, "length": len(line)} for idx, line in enumerate(lines)],
        }
        return NormalizedDocument(text="\n".join(lines), tokens=tokens, layout_metadata=layout)

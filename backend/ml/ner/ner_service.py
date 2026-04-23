"""
NER Service for Indian tax documents.

Architecture
------------
1. REGEX layer (PRIMARY) — deterministic, always runs, extracts exact fields.
2. XLM-RoBERTa transformer (OPTIONAL) — enriches soft fields (names, dates).
   Only runs if the model is available locally; never blocks the pipeline.

The regex layer is the source of truth for:
  PAN, TAN, AssessmentYear, GrossSalary, TaxableIncome, TDS, 80C, 80D

The transformer may supplement:
  EmployerName, EmployeeName (when regex misses them)

Output
------
{
    "entities": [
        {"label": "PAN",          "value": "BIGPP1846N", "confidence": 1.0},
        {"label": "TAN",          "value": "MUMS15654C", "confidence": 1.0},
        {"label": "GrossSalary",  "value": "873898.0",   "confidence": 1.0},
        ...
    ],
    "entity_map": {
        "PAN": "BIGPP1846N",
        "TAN": "MUMS15654C",
        "GrossSalary": 873898.0,
        ...
    }
}
"""

import logging
from typing import Any, Dict, List, Optional

from .regex_utils import extract_fields, extract_all as regex_extract_all

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label schema (kept for future fine-tuning)
# ---------------------------------------------------------------------------
LABEL_LIST: List[str] = [
    "O",
    "B-PAN",        "I-PAN",
    "B-TAN",        "I-TAN",
    "B-EmployerName",  "I-EmployerName",
    "B-EmployeeName",  "I-EmployeeName",
    "B-GrossSalary",   "I-GrossSalary",
    "B-NetSalary",     "I-NetSalary",
    "B-Section80C",    "I-Section80C",
    "B-Section80D",    "I-Section80D",
    "B-TDS",           "I-TDS",
    "B-TaxableIncome", "I-TaxableIncome",
]

LABEL2ID: Dict[str, int] = {lbl: idx for idx, lbl in enumerate(LABEL_LIST)}
ID2LABEL: Dict[int, str] = {idx: lbl for lbl, idx in LABEL2ID.items()}


class NERService:
    """Hybrid NER: regex (primary) + optional transformer (supplementary)."""

    def __init__(
        self,
        model_name_or_path: str = "xlm-roberta-base",
        device: int = -1,
        confidence_threshold: float = 0.60,
        use_transformer: bool = False,   # disabled by default — requires fine-tuned model
    ):
        self.confidence_threshold = confidence_threshold
        self.ner_pipeline = None

        if use_transformer:
            try:
                import torch
                from transformers import (
                    AutoTokenizer,
                    AutoModelForTokenClassification,
                    pipeline,
                )
                log.info("Loading NER transformer: %s …", model_name_or_path)
                tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
                model = AutoModelForTokenClassification.from_pretrained(
                    model_name_or_path,
                    num_labels=len(LABEL_LIST),
                    id2label=ID2LABEL,
                    label2id=LABEL2ID,
                    ignore_mismatched_sizes=True,
                )
                self.ner_pipeline = pipeline(
                    task="ner",
                    model=model,
                    tokenizer=tokenizer,
                    aggregation_strategy="simple",
                    device=device,
                )
                log.info("Transformer NER ready.")
            except Exception as exc:
                log.warning(
                    "Transformer NER unavailable (%s) — regex-only mode.", exc
                )

        log.info(
            "NERService initialised — transformer=%s, threshold=%.2f",
            self.ner_pipeline is not None,
            confidence_threshold,
        )

    # ------------------------------------------------------------------
    # Transformer runner (optional supplement)
    # ------------------------------------------------------------------
    def _run_transformer(self, text: str) -> List[Dict[str, Any]]:
        if self.ner_pipeline is None:
            return []
        try:
            raw = self.ner_pipeline(text[:512])  # BERT max token safety
            entities = []
            for ent in raw:
                label = ent.get("entity_group", "")
                score = float(ent.get("score", 0))
                if score < self.confidence_threshold:
                    continue
                entities.append({
                    "label": label,
                    "value": ent["word"].strip(),
                    "confidence": round(score, 4),
                    "source": "transformer",
                })
            log.info("[NER] Transformer entities above threshold: %d", len(entities))
            return entities
        except Exception as exc:
            log.warning("[NER] Transformer inference failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, text: str) -> Dict[str, Any]:
        """Run the full NER pipeline.

        Returns
        -------
        dict with keys:
            entities  : list of {label, value, confidence}
            entity_map: flat dict with exact validation field names
        """
        if not text or not text.strip():
            log.warning("[NER] Empty text — returning empty result.")
            return {"entities": [], "entity_map": {}}

        log.info("[NER] Text length: %d chars", len(text))
        log.debug("[NER] TEXT SAMPLE: %s", text[:500])

        # ── Step 1: Regex (deterministic, always runs) ──────────────────
        entity_map: Dict[str, Any] = extract_fields(text)
        log.info("[NER] REGEX entity_map: %s", entity_map)

        # ── Step 2: Transformer (optional, supplements soft fields) ──────
        transformer_entities = self._run_transformer(text)
        for ent in transformer_entities:
            lbl = ent["label"]
            # Only supplement fields not already found by regex
            if lbl not in entity_map and lbl in (
                "EmployerName", "EmployeeName", "AssessmentYear"
            ):
                entity_map[lbl] = ent["value"]
                log.info("[NER] Transformer supplemented: %s = %s", lbl, ent["value"])

        # ── Step 3: Coerce numeric fields to float ───────────────────────
        numeric_fields = {"GrossSalary", "TaxableIncome", "TDS", "Section80C", "Section80D"}
        for field in numeric_fields:
            if field in entity_map:
                try:
                    val = str(entity_map[field]).replace(",", "")
                    entity_map[field] = float(val)
                except (ValueError, TypeError):
                    log.warning("[NER] Could not coerce %s='%s' to float", field, entity_map[field])

        log.info("[NER] FINAL entity_map: %s", entity_map)

        # ── Step 4: Build entity list for API response ───────────────────
        entities: List[Dict[str, Any]] = []
        for label, value in entity_map.items():
            entities.append({
                "label": label,
                "value": str(value),
                "confidence": 1.0,
            })

        return {
            "entities": entities,
            "entity_map": entity_map,
        }

    # ------------------------------------------------------------------
    # Placeholder training pipeline (future fine-tuning)
    # ------------------------------------------------------------------
    def placeholder_train(
        self,
        train_dataset: Any,
        eval_dataset: Optional[Any] = None,
        output_dir: str = "./ner_checkpoints",
        epochs: int = 5,
        batch_size: int = 16,
        learning_rate: float = 2e-5,
    ) -> None:
        """Placeholder for future fine-tuning with annotated tax documents."""
        try:
            import torch
            from transformers import TrainingArguments, Trainer

            if self.ner_pipeline is None:
                raise RuntimeError("No model loaded — init with use_transformer=True")

            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                learning_rate=learning_rate,
                weight_decay=0.01,
                eval_strategy="epoch" if eval_dataset else "no",
                save_strategy="epoch",
                logging_steps=50,
                load_best_model_at_end=bool(eval_dataset),
                fp16=torch.cuda.is_available(),
            )
            trainer = Trainer(
                model=self.ner_pipeline.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                tokenizer=self.ner_pipeline.tokenizer,
            )
            log.info("Starting NER fine-tuning — %d epochs", epochs)
            trainer.train()
            trainer.save_model(output_dir)
            log.info("Training complete — saved to %s", output_dir)
        except Exception as exc:
            log.exception("Training failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------
def run_inference(text: str) -> Dict[str, Any]:
    """One-shot NER inference using regex-primary pipeline."""
    return NERService().extract(text)

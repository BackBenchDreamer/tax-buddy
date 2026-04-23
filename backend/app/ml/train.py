from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.ml.schema import ENTITY_LABELS


@dataclass
class TrainingConfig:
    model_name: str = "xlm-roberta-base"
    output_dir: Path = Path("./storage/models/xlm-roberta-tax-ner")
    epochs: int = 5
    batch_size: int = 8
    max_length: int = 256
    learning_rate: float = 2e-5


class NerTrainer:
    """Transformer fine-tuning pipeline for Indian tax document NER."""

    def build_training_payload(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "label_list": ENTITY_LABELS,
            "samples": samples,
            "notes": [
                "Use wordpiece-aligned BIO tags for token classification.",
                "Separate PAN/TAN/monetary spans from contextual labels.",
            ],
        }

    def train(self, config: TrainingConfig, dataset_path: Path) -> Path:
        try:
            from datasets import Dataset
            from transformers import (
                AutoModelForTokenClassification,
                AutoTokenizer,
                DataCollatorForTokenClassification,
                Trainer,
                TrainingArguments,
            )
        except Exception as exc:  # pragma: no cover - dependency optional in lightweight runs
            raise RuntimeError("transformers stack is required to run training") from exc

        tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        model = AutoModelForTokenClassification.from_pretrained(
            config.model_name,
            num_labels=len(ENTITY_LABELS),
            id2label={idx: label for idx, label in enumerate(ENTITY_LABELS)},
            label2id={label: idx for idx, label in enumerate(ENTITY_LABELS)},
        )

        raw_dataset = Dataset.from_json(str(dataset_path))

        def tokenize_and_align_labels(examples: dict[str, list[Any]]) -> dict[str, Any]:
            tokenized = tokenizer(
                examples["tokens"],
                is_split_into_words=True,
                truncation=True,
                max_length=config.max_length,
            )
            aligned_labels: list[list[int]] = []
            for batch_index, labels in enumerate(examples["ner_tags"]):
                word_ids = tokenized.word_ids(batch_index=batch_index)
                previous_word_id = None
                label_ids: list[int] = []
                for word_id in word_ids:
                    if word_id is None:
                        label_ids.append(-100)
                    elif word_id != previous_word_id:
                        label_ids.append(labels[word_id])
                    else:
                        label_ids.append(-100)
                    previous_word_id = word_id
                aligned_labels.append(label_ids)
            tokenized["labels"] = aligned_labels
            return tokenized

        tokenized_dataset = raw_dataset.map(tokenize_and_align_labels, batched=True)

        args = TrainingArguments(
            output_dir=str(config.output_dir),
            learning_rate=config.learning_rate,
            per_device_train_batch_size=config.batch_size,
            per_device_eval_batch_size=config.batch_size,
            num_train_epochs=config.epochs,
            weight_decay=0.01,
            logging_steps=25,
            save_strategy="epoch",
            evaluation_strategy="no",
        )

        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=tokenized_dataset,
            tokenizer=tokenizer,
            data_collator=DataCollatorForTokenClassification(tokenizer),
        )
        trainer.train()
        trainer.save_model(str(config.output_dir))
        tokenizer.save_pretrained(str(config.output_dir))
        return config.output_dir

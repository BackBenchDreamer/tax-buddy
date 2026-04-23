"""
Training pipeline for the Tax NER model.
Run: python -m app.ml.train --train data/train.conll --val data/val.conll --output data/models/ner
"""
from __future__ import annotations
import argparse
from pathlib import Path
from transformers import (
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification,
)
from app.ml.dataset import build_dataset, tokenize_and_align_labels, LABEL_LIST
from app.ml.ner_model import create_model
from app.ml.evaluate import compute_metrics_fn


def train(
    model_name: str,
    train_path: str,
    val_path: str,
    output_dir: str,
    epochs: int = 5,
    batch_size: int = 16,
    lr: float = 2e-5,
):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    raw_datasets = build_dataset(train_path, val_path)

    tokenized_datasets = raw_datasets.map(
        lambda ex: tokenize_and_align_labels(ex, tokenizer),
        batched=True,
        remove_columns=["tokens", "ner_tags"],
    )

    model = create_model(model_name)
    data_collator = DataCollatorForTokenClassification(tokenizer)

    args = TrainingArguments(
        output_dir=output_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=lr,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        num_train_epochs=epochs,
        weight_decay=0.01,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir=f"{output_dir}/logs",
        fp16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=lambda p: compute_metrics_fn(p, LABEL_LIST),
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model saved to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="xlm-roberta-base")
    parser.add_argument("--train", required=True)
    parser.add_argument("--val", required=True)
    parser.add_argument("--output", default="data/models/ner")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()
    train(args.model, args.train, args.val, args.output, args.epochs, args.batch_size, args.lr)

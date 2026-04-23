"""
Dataset utilities for NER model training.
Expected format: CoNLL-2003 style with BIO tags.

Entity labels:
  B-PAN, I-PAN
  B-TAN, I-TAN
  B-ENAME (employee name)
  B-ONAME (employer/org name)
  B-SALARY
  B-TDS
  B-DEDUCTION
  B-AY (assessment year)
  O
"""
from __future__ import annotations
import json
from pathlib import Path
from datasets import Dataset, DatasetDict
from transformers import AutoTokenizer

LABEL_LIST = [
    "O",
    "B-PAN", "I-PAN",
    "B-TAN", "I-TAN",
    "B-ENAME", "I-ENAME",
    "B-ONAME", "I-ONAME",
    "B-SALARY", "I-SALARY",
    "B-TDS", "I-TDS",
    "B-DEDUCTION", "I-DEDUCTION",
    "B-AY", "I-AY",
]
LABEL2ID = {l: i for i, l in enumerate(LABEL_LIST)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}


def load_conll_file(path: str) -> list[dict]:
    """Load a CoNLL-format file into a list of {"tokens": [...], "ner_tags": [...]}."""
    samples = []
    tokens, tags = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                if tokens:
                    samples.append({"tokens": tokens, "ner_tags": [LABEL2ID.get(t, 0) for t in tags]})
                    tokens, tags = [], []
            else:
                parts = line.split()
                tokens.append(parts[0])
                tags.append(parts[-1] if len(parts) > 1 else "O")
    if tokens:
        samples.append({"tokens": tokens, "ner_tags": [LABEL2ID.get(t, 0) for t in tags]})
    return samples


def load_json_annotated(path: str) -> list[dict]:
    """
    Load JSON annotated data.
    Format: [{"tokens": ["ABCDE", "1234F", ...], "ner_tags": ["B-PAN", "I-PAN", ...]}]
    """
    with open(path) as f:
        data = json.load(f)
    return [{"tokens": d["tokens"], "ner_tags": [LABEL2ID.get(t, 0) for t in d["ner_tags"]]} for d in data]


def build_dataset(train_path: str, val_path: str, test_path: str | None = None) -> DatasetDict:
    train = Dataset.from_list(load_conll_file(train_path))
    val = Dataset.from_list(load_conll_file(val_path))
    splits = {"train": train, "validation": val}
    if test_path:
        splits["test"] = Dataset.from_list(load_conll_file(test_path))
    return DatasetDict(splits)


def tokenize_and_align_labels(examples: dict, tokenizer, label_all_tokens: bool = False) -> dict:
    tokenized = tokenizer(
        examples["tokens"],
        truncation=True,
        is_split_into_words=True,
        max_length=512,
    )
    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized.word_ids(batch_index=i)
        prev_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != prev_word_idx:
                label_ids.append(label[word_idx])
            else:
                label_ids.append(label[word_idx] if label_all_tokens else -100)
            prev_word_idx = word_idx
        labels.append(label_ids)
    tokenized["labels"] = labels
    return tokenized


def create_sample_annotation() -> list[dict]:
    """Create a sample annotated dataset entry for demonstration."""
    return [
        {
            "tokens": ["PAN", ":", "ABCDE1234F", "TAN", ":", "MUMH12345G",
                       "Gross", "Salary", ":", "1200000", "TDS", ":", "95000"],
            "ner_tags": ["O", "O", "B-PAN", "O", "O", "B-TAN",
                         "B-SALARY", "I-SALARY", "O", "I-SALARY", "B-TDS", "O", "I-TDS"]
        }
    ]

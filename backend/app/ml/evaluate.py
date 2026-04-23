"""
Evaluation metrics for NER using seqeval (Precision, Recall, F1, Accuracy).
"""
import numpy as np
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score


def compute_metrics_fn(p, label_list: list[str]) -> dict:
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    true_predictions = [
        [label_list[pred] for pred, lab in zip(prediction, label) if lab != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [label_list[lab] for lab in label if lab != -100]
        for label in labels
    ]

    return {
        "precision": precision_score(true_labels, true_predictions),
        "recall": recall_score(true_labels, true_predictions),
        "f1": f1_score(true_labels, true_predictions),
        "report": classification_report(true_labels, true_predictions),
    }

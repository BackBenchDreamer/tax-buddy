"""
NER model definition and configuration for fine-tuning XLM-RoBERTa.
"""
from transformers import AutoModelForTokenClassification, AutoConfig
from app.ml.dataset import LABEL_LIST, LABEL2ID, ID2LABEL


def create_model(model_name: str = "xlm-roberta-base") -> AutoModelForTokenClassification:
    config = AutoConfig.from_pretrained(
        model_name,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    model = AutoModelForTokenClassification.from_pretrained(model_name, config=config, ignore_mismatched_sizes=True)
    return model

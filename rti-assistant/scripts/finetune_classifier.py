"""
Fine-tune a DistilBERT classifier on the labeled RTI case dataset.

Trains a sequence classification model with 4 labels:
  ALLOWED, PARTIAL, DENIED, TRANSFERRED

Saves the fine-tuned model to models/rti_classifier/
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import torch

# Optional imports — only fail gracefully if missing
try:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
    )
    from datasets import Dataset
    import evaluate
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

MODEL_DIR = PROJECT_ROOT / "models" / "rti_classifier"
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "rti_cases_labeled.csv"

LABEL_LIST = ["ALLOWED", "PARTIAL", "DENIED", "TRANSFERRED"]
LABEL2ID = {l: i for i, l in enumerate(LABEL_LIST)}
ID2LABEL = {i: l for i, l in enumerate(LABEL_LIST)}

BASE_MODEL = "distilbert-base-uncased"


def load_data():
    """
    Load labeled RTI cases and prepare train/test splits.

    Returns:
        Tuple of (train_df, test_df) DataFrames.
    """
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["decision", "label"])
    df = df[df["label"].isin(LABEL_LIST)]
    df["text"] = df["background"].fillna("") + " " + df["decision"].fillna("")
    df["label_id"] = df["label"].map(LABEL2ID)

    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
    print(f"[finetune] Train: {len(train_df)}, Test: {len(test_df)}")
    return train_df, test_df


def tokenize_dataset(tokenizer, df: pd.DataFrame) -> Dataset:
    """
    Tokenize a DataFrame into a HuggingFace Dataset.

    Args:
        tokenizer: HuggingFace tokenizer.
        df: DataFrame with 'text' and 'label_id' columns.

    Returns:
        HuggingFace Dataset ready for training.
    """
    hf_dataset = Dataset.from_pandas(df[["text", "label_id"]].reset_index(drop=True))

    def tokenize_fn(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=256,
        )

    hf_dataset = hf_dataset.map(tokenize_fn, batched=True)
    hf_dataset = hf_dataset.rename_column("label_id", "labels")
    hf_dataset.set_format("torch", columns=["input_ids", "attention_mask", "labels"])
    return hf_dataset


def compute_metrics(eval_pred):
    """
    Compute accuracy and F1 for Trainer evaluation.

    Args:
        eval_pred: EvalPrediction from Trainer.

    Returns:
        Dict with accuracy and f1 scores.
    """
    accuracy_metric = evaluate.load("accuracy")
    f1_metric = evaluate.load("f1")

    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)

    acc = accuracy_metric.compute(predictions=predictions, references=labels)
    f1 = f1_metric.compute(predictions=predictions, references=labels, average="weighted")
    return {**acc, **f1}


def run_finetune():
    """
    Full fine-tuning pipeline for the RTI classifier.

    Checks dependencies, loads data, fine-tunes DistilBERT,
    and saves the model to models/rti_classifier/.
    """
    if not TRANSFORMERS_AVAILABLE:
        print("[finetune] ERROR: transformers / datasets not installed.")
        print("[finetune] Run: pip install transformers datasets evaluate")
        sys.exit(1)

    if not DATA_PATH.exists():
        print(f"[finetune] ERROR: Labeled data not found at {DATA_PATH}")
        print("[finetune] Run: python scripts/download_datasets.py first.")
        sys.exit(1)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[finetune] Loading base model: {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(LABEL_LIST),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    print("[finetune] Loading and tokenizing data...")
    train_df, test_df = load_data()
    train_dataset = tokenize_dataset(tokenizer, train_df)
    eval_dataset = tokenize_dataset(tokenizer, test_df)

    # Limit training size to speed up for demonstration
    max_train = min(len(train_dataset), 2000)
    max_eval = min(len(eval_dataset), 400)
    train_dataset = train_dataset.select(range(max_train))
    eval_dataset = eval_dataset.select(range(max_eval))

    print(f"[finetune] Training on {max_train} samples, evaluating on {max_eval} samples.")

    training_args = TrainingArguments(
        output_dir=str(MODEL_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        warmup_steps=50,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_dir=str(MODEL_DIR / "logs"),
        logging_steps=50,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics,
    )

    print("[finetune] Starting training...")
    trainer.train()

    print(f"[finetune] Saving model to {MODEL_DIR} ...")
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    # Final evaluation
    metrics = trainer.evaluate()
    print("\n[finetune] Final evaluation metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print(f"\n[finetune] Model saved to: {MODEL_DIR}")
    print("[finetune] Fine-tuning complete!")


if __name__ == "__main__":
    run_finetune()

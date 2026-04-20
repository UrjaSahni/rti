"""
Evaluation: RTI Response Classifier.

Tests classification accuracy on the labeled RTI case dataset.
Tries fine-tuned DistilBERT first; falls back to keyword classifier.
"""
import json
import sys
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "rti_cases_labeled.csv"
MODEL_DIR = PROJECT_ROOT / "models" / "rti_classifier"

LABEL_LIST = ["ALLOWED", "PARTIAL", "DENIED", "TRANSFERRED"]


def _keyword_classify(text: str) -> str:
    """
    Keyword-based fallback classifier.

    Args:
        text: Decision text to classify.

    Returns:
        One of: ALLOWED, TRANSFERRED, DENIED, PARTIAL.
    """
    t = text.lower()
    if any(w in t for w in ["transferred", "transfer the application"]):
        return "TRANSFERRED"
    if any(w in t for w in ["exempt", "section 8", "cannot be provided", "denied"]):
        return "DENIED"
    if any(w in t for w in ["directed to provide", "shall provide", "disclose",
                              "information be provided", "furnish"]):
        return "ALLOWED"
    return "PARTIAL"


def _try_load_model():
    """
    Attempt to load the fine-tuned DistilBERT model.

    Returns:
        Tuple of (tokenizer, model) or (None, None) if not found.
    """
    if not MODEL_DIR.exists():
        return None, None
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
        model.eval()
        print("[eval_classifier] Fine-tuned model loaded from", MODEL_DIR)
        return tokenizer, model
    except Exception as e:
        print(f"[eval_classifier] Could not load fine-tuned model: {e}. Using keyword fallback.")
        return None, None


def _model_predict(tokenizer, model, texts):
    """
    Run batch predictions using the fine-tuned model.

    Args:
        tokenizer: HuggingFace tokenizer.
        model: Fine-tuned classification model.
        texts: List of text strings to classify.

    Returns:
        List of predicted label strings.
    """
    import torch
    id2label = model.config.id2label
    predictions = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=256,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
        preds = outputs.logits.argmax(dim=-1).tolist()
        predictions.extend([id2label[p] for p in preds])
    return predictions


def run_classifier_eval() -> Dict:
    """
    Evaluate the RTI response classifier on the labeled test set.

    Tries fine-tuned DistilBERT first; uses keyword classifier as fallback.
    Computes accuracy, F1-weighted, and saves confusion matrix.

    Returns:
        Dict with status (PASS/FAIL), accuracy, f1.
    """
    import pandas as pd
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score, f1_score, confusion_matrix, classification_report
    )

    if not DATA_PATH.exists():
        print(f"[eval_classifier] Data file not found: {DATA_PATH}")
        print("[eval_classifier] Run: python scripts/download_datasets.py first.")
        result = {"status": "FAIL", "accuracy": 0.0, "f1": 0.0,
                  "error": "Data file missing"}
        with open(RESULTS_DIR / "classifier_eval.json", "w") as f:
            json.dump(result, f, indent=2)
        return result

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["decision", "label"])
    df = df[df["label"].isin(LABEL_LIST)]
    df["text"] = df["background"].fillna("") + " " + df["decision"].fillna("")

    _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])
    print(f"[eval_classifier] Test set size: {len(test_df)}")

    tokenizer, model = _try_load_model()

    if model is not None and tokenizer is not None:
        print("[eval_classifier] Running model predictions...")
        y_pred = _model_predict(tokenizer, model, test_df["text"].tolist())
        classifier_type = "fine-tuned DistilBERT"
    else:
        print("[eval_classifier] Running keyword-based classification...")
        y_pred = [_keyword_classify(t) for t in test_df["decision"].tolist()]
        classifier_type = "keyword-based fallback"

    y_true = test_df["label"].tolist()

    accuracy = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=LABEL_LIST)
    report = classification_report(y_true, y_pred, labels=LABEL_LIST, zero_division=0)

    print(f"\n[eval_classifier] Classifier type: {classifier_type}")
    print(f"[eval_classifier] Accuracy: {accuracy:.4f}")
    print(f"[eval_classifier] F1 (weighted): {f1:.4f}")
    print("\n" + report)

    # Save confusion matrix plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(
            cm, annot=True, fmt="d", xticklabels=LABEL_LIST, yticklabels=LABEL_LIST,
            cmap="Blues", ax=ax,
        )
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_title(f"RTI Classifier — Confusion Matrix ({classifier_type})")
        plt.tight_layout()
        fig.savefig(str(RESULTS_DIR / "confusion_matrix.png"), dpi=120)
        plt.close(fig)
        print(f"[eval_classifier] Confusion matrix saved: {RESULTS_DIR}/confusion_matrix.png")
    except Exception as e:
        print(f"[eval_classifier] Could not save plot: {e}")

    status = "PASS" if accuracy >= 0.7 else "FAIL"
    output = {
        "status": status,
        "accuracy": round(accuracy, 4),
        "f1": round(f1, 4),
        "classifier_type": classifier_type,
        "test_size": len(test_df),
        "confusion_matrix": cm.tolist(),
        "labels": LABEL_LIST,
    }

    out_path = RESULTS_DIR / "classifier_eval.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n[eval_classifier] {status} | Accuracy: {accuracy:.4f} | F1: {f1:.4f}")
    print(f"[eval_classifier] Results saved: {out_path}")
    return output


if __name__ == "__main__":
    run_classifier_eval()

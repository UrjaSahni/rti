"""
Download and preprocess the HuggingFace RTI Case Dataset.

Actions:
  1. Load jatinmehra/RTI-CASE-DATASET (public — no token needed)
  2. Auto-label each case using keyword matching
  3. Save labeled CSV to DATASET/processed/rti_cases_labeled.csv
  4. Save each case as a .txt file in DATASET/cic_orders/
"""
import re
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from datasets import load_dataset
from tqdm import tqdm


DATA_PROCESSED = PROJECT_ROOT.parent / "DATASET" / "processed"
CIC_ORDERS_DIR = PROJECT_ROOT.parent / "DATASET" / "cic_orders"
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
CIC_ORDERS_DIR.mkdir(parents=True, exist_ok=True)


def classify_decision(text: str) -> str:
    """
    Classify a CIC decision text using keyword matching.

    Args:
        text: The decision text from the dataset.

    Returns:
        Label: "ALLOWED", "TRANSFERRED", "DENIED", or "PARTIAL".
    """
    t = text.lower()
    if any(w in t for w in ["transferred", "transfer the application", "transfer to"]):
        return "TRANSFERRED"
    if any(w in t for w in ["exempt", "section 8", "cannot be provided",
                              "not maintainable", "denied", "reject", "no information"]):
        return "DENIED"
    if any(w in t for w in ["directed to provide", "shall provide", "disclose",
                              "is hereby provided", "order to provide", "information be provided",
                              "supply the information", "furnish the information"]):
        return "ALLOWED"
    return "PARTIAL"


def download_and_label():
    """
    Download the RTI Case Dataset, label it, and save output files.

    Prints progress throughout. Saves:
    - data/processed/rti_cases_labeled.csv
    - data/raw/cic_orders/<n>.txt  (one file per case)
    """
    print("Loading HuggingFace dataset: jatinmehra/RTI-CASE-DATASET ...")
    try:
        dataset = load_dataset("jatinmehra/RTI-CASE-DATASET", trust_remote_code=True)
    except Exception as e:
        print(f"ERROR loading dataset: {e}")
        print("Check your internet connection. The dataset is public — no token required.")
        sys.exit(1)

    # Try the default split
    if "train" in dataset:
        data = dataset["train"]
    else:
        data = dataset[list(dataset.keys())[0]]

    print(f"Dataset loaded: {len(data)} records.")

    rows = []
    for i, item in enumerate(tqdm(data, desc="Labelling cases")):
        background = item.get("background", item.get("Background", ""))
        decision = item.get("decision", item.get("Decision", ""))

        if not background and not decision:
            continue

        label = classify_decision(decision)
        rows.append({
            "case_id": i,
            "background": background,
            "decision": decision,
            "label": label,
        })

        # Save as .txt for RAG indexing
        case_text = f"Background: {background}\nDecision: {decision}"
        txt_path = CIC_ORDERS_DIR / f"case_{i:05d}.txt"
        txt_path.write_text(case_text, encoding="utf-8")

    df = pd.DataFrame(rows)
    csv_path = DATA_PROCESSED / "rti_cases_labeled.csv"
    df.to_csv(csv_path, index=False)

    label_counts = df["label"].value_counts().to_dict()
    print(f"\nLabeling complete:")
    print(f"  Total cases: {len(df)}")
    for label, count in label_counts.items():
        print(f"  {label}: {count}")
    print(f"\nSaved: {csv_path}")
    print(f"Saved: {len(rows)} .txt files in {CIC_ORDERS_DIR}")


if __name__ == "__main__":
    download_and_label()

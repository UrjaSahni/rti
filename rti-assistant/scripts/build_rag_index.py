"""
Build the ChromaDB RAG index from:
  1. DATASET/RTI-Act_English.pdf → rti_act_chunks collection
  2. data/raw/cic_orders/*.txt   → rti_case_chunks collection

Run this script after download_datasets.py.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag.indexer import build_index


if __name__ == "__main__":
    print("=" * 60)
    print("Building ChromaDB RAG Index")
    print("=" * 60)

    result = build_index()

    print("\n" + "=" * 60)
    print("Index build complete.")
    print(f"  RTI Act chunks  : {result['act_chunks']}")
    print(f"  CIC Case chunks : {result['case_chunks']}")
    print(f"  Total           : {result['act_chunks'] + result['case_chunks']}")
    print("=" * 60)
    print("\nNext step: start the API server with:")
    print("  uvicorn app.main:app --reload")

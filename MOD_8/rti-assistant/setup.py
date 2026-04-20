"""
Setup script — installs dependencies, downloads datasets, seeds the database,
and builds the ChromaDB RAG index in the correct order.

Run this once after cloning the repository and setting up .env.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_command(cmd: list, description: str) -> bool:
    """
    Run a subprocess command and stream output.

    Args:
        cmd: Command as a list of strings.
        description: Human-readable description.

    Returns:
        True if successful, False otherwise.
    """
    print(f"\n{'=' * 60}")
    print(f"STEP: {description}")
    print(f"{'=' * 60}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"[ERROR] Failed: {description}")
        return False
    print(f"[OK] Completed: {description}")
    return True


def check_env():
    """
    Verify .env file exists and contains non-placeholder API keys.

    Exits with a helpful message if keys are missing.
    """
    env_path = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"

    if not env_path.exists():
        if env_example.exists():
            import shutil
            shutil.copy(str(env_example), str(env_path))
            print("Created .env from .env.example")
        print("\n" + "=" * 60)
        print("ACTION REQUIRED: Fill in your API keys in .env")
        print("  OPENAI_API_KEY  → get from platform.openai.com (free)")
        print("  GROQ_API_KEY    → get from console.groq.com (free)")
        print("\nThen run: python setup.py")
        print("=" * 60)
        sys.exit(1)

    # Load and validate keys
    from dotenv import dotenv_values
    config = dotenv_values(str(env_path))

    openai_key = config.get("OPENAI_API_KEY", "")
    groq_key = config.get("GROQ_API_KEY", "")

    placeholder_prefixes = ("your_", "YOUR_", "sk-placeholder", "gsk_placeholder", "")

    def is_placeholder(key: str) -> bool:
        return not key or any(key.startswith(p) for p in placeholder_prefixes)

    if is_placeholder(openai_key) or is_placeholder(groq_key):
        print("\n" + "=" * 60)
        print("ACTION REQUIRED: API keys not set in .env")
        print(f"  OPENAI_API_KEY  = {'SET ✓' if not is_placeholder(openai_key) else 'MISSING ✗'}")
        print(f"  GROQ_API_KEY    = {'SET ✓' if not is_placeholder(groq_key) else 'MISSING ✗'}")
        print("\nGet your free keys:")
        print("  OpenAI: https://platform.openai.com/api-keys")
        print("  Groq:   https://console.groq.com/keys")
        print("\nThen run: python setup.py")
        print("=" * 60)
        sys.exit(1)

    print("[OK] API keys validated.")


def check_rti_pdf():
    """
    Verify that the RTI Act PDF is present in DATASET folder.

    Exits with a clear error if missing.
    """
    pdf_path = PROJECT_ROOT.parent / "DATASET" / "RTI-Act_English.pdf"
    if not pdf_path.exists():
        print("\n" + "=" * 60)
        print("ERROR: RTI Act PDF not found!")
        print(f"Expected at: {pdf_path}")
        print("\nDownload the RTI Act 2005 PDF and place it at:")
        print("  DATASET/RTI-Act_English.pdf")
        print("\nSource: https://rti.gov.in/rti-act.pdf")
        print("=" * 60)
        sys.exit(1)
    print(f"[OK] RTI Act PDF found: {pdf_path}")


def main():
    """Run the full setup pipeline in order."""
    print("\n" + "=" * 60)
    print("RTI Query Assistant — Setup")
    print("=" * 60)

    # Step 1: Check .env
    print("\n[Step 1] Checking environment configuration...")
    check_env()

    # Step 2: Check RTI PDF
    print("\n[Step 2] Checking RTI Act PDF...")
    check_rti_pdf()

    # Step 3: Install requirements
    print("\n[Step 3] Installing Python packages...")
    ok = run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "pip install -r requirements.txt",
    )
    if not ok:
        print("[WARN] Some packages may have failed. Continuing...")

    # Step 4: Download + label HuggingFace dataset
    print("\n[Step 4] Downloading RTI case dataset from HuggingFace...")
    ok = run_command(
        [sys.executable, "scripts/download_datasets.py"],
        "Download and label RTI case dataset",
    )
    if not ok:
        print("[WARN] Dataset download failed. RAG may use only the RTI Act PDF.")

    # Step 5: Seed database
    print("\n[Step 5] Seeding the SQLite database...")
    ok = run_command(
        [sys.executable, "scripts/seed_database.py"],
        "Seed departments, citizens, and applications",
    )
    if not ok:
        print("[ERROR] Database seeding failed. Check the error above.")
        sys.exit(1)

    # Step 6: Build RAG index
    print("\n[Step 6] Building ChromaDB RAG index...")
    ok = run_command(
        [sys.executable, "scripts/build_rag_index.py"],
        "Index RTI Act + CIC cases in ChromaDB",
    )
    if not ok:
        print("[WARN] RAG index build failed. The API will warn at startup.")

    # Done
    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print("\nNext steps:")
    print("")
    print("  1. Start the API server:")
    print("     uvicorn app.main:app --reload")
    print("     (API available at http://localhost:8000)")
    print("     (Docs at http://localhost:8000/docs)")
    print("")
    print("  2. Start the Streamlit UI (in a separate terminal):")
    print("     streamlit run frontend/streamlit_app.py")
    print("     (UI available at http://localhost:8501)")
    print("")
    print("  3. (Optional) Run all evaluations:")
    print("     python evaluation/run_all_evals.py")
    print("")
    print("  4. (Optional) Fine-tune the classifier:")
    print("     python scripts/finetune_classifier.py")
    print("=" * 60)


if __name__ == "__main__":
    main()

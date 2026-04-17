"""
Application configuration using pydantic-settings.
Loads all environment variables with validation.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path

# Project root resolved at import time — used for absolute default paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.

    Attributes:
        openai_api_key: OpenAI API key for fallback LLM and PDF OCR.
        groq_api_key: Groq API key for primary LLM (llama-3.1-70b-versatile).
        database_url: SQLAlchemy-compatible database URL.
        chroma_path: Path to ChromaDB persistence directory.
        model_path: Path to fine-tuned DistilBERT classifier.
        environment: Runtime environment (development/production).
    """

    # Suppress pydantic's "model_" namespace warning for model_path field
    # Use absolute path so .env is found regardless of working directory
    model_config = ConfigDict(
        protected_namespaces=("settings_",),
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    openai_api_key: str = ""
    groq_api_key: str = ""
    # Absolute defaults so the DB/ChromaDB are always found regardless of CWD
    database_url: str = f"sqlite:///{_PROJECT_ROOT}/rti_tracker.db"
    chroma_path: str = str(_PROJECT_ROOT / "chroma_store")
    model_path: str = str(_PROJECT_ROOT / "models" / "rti_classifier")
    environment: str = "development"


settings = Settings()

# Derived path objects used across the application
BASE_DIR = _PROJECT_ROOT
DATASET_DIR = BASE_DIR.parent / "DATASET"          # shared dataset folder
DATA_PROCESSED_DIR = DATASET_DIR / "processed"     # labeled CSV output
CIC_ORDERS_DIR = DATASET_DIR / "cic_orders"        # CIC case .txt files
DATA_RAW_DIR = DATASET_DIR                          # kept for backward-compat imports
CHROMA_DIR = Path(settings.chroma_path)
MODEL_DIR = Path(settings.model_path)

"""
Government response parsing route — accepts PDF upload or plain text,
classifies the response, and returns structured classification result.

REFACTORED: No database dependency. Returns raw_text for appeal generation.
"""
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pathlib import Path
import shutil
import uuid

from app.database.schemas import ClassificationResult
from app.agents.response_agent import run_response_agent

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "DATASET" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/parse-response", response_model=ClassificationResult)
async def parse_response(
    response_text: Optional[str] = Form(None),
    pdf_file: Optional[UploadFile] = File(None),
):
    """
    Parse and classify a government RTI response.

    Accepts either a PDF file upload or plain response text.
    At least one must be provided.
    
    NO DATABASE DEPENDENCY — returns classification + raw_text for appeal generation.

    Args:
        response_text: Optional plain text response content.
        pdf_file: Optional PDF file upload.

    Returns:
        ClassificationResult with classification, confidence, summary,
        recommended action, and raw_text for appeal generation.
    """
    if not pdf_file and not response_text:
        raise HTTPException(
            status_code=400,
            detail="Provide either a PDF file or response_text.",
        )

    saved_pdf_path: Optional[str] = None

    # Save uploaded PDF
    if pdf_file and pdf_file.filename:
        ext = Path(pdf_file.filename).suffix or ".pdf"
        filename = f"{uuid.uuid4().hex}{ext}"
        save_path = UPLOAD_DIR / filename
        with save_path.open("wb") as f:
            shutil.copyfileobj(pdf_file.file, f)
        saved_pdf_path = str(save_path)

    try:
        result = run_response_agent(
            pdf_path=saved_pdf_path,
            response_text=response_text,
        )
        return ClassificationResult(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

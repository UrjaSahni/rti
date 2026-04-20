"""
PDF text extraction utility.

Attempts three extraction methods in order:
1. pdfplumber  — works on most digital PDFs
2. PyMuPDF (fitz) — faster alternative for digital PDFs
3. OpenAI Vision API (gpt-4o-mini) — fallback for scanned/image PDFs
"""
import base64
import io
from pathlib import Path
from typing import Optional

import pdfplumber
import fitz  # PyMuPDF
from openai import OpenAI

from app.config import settings


def _extract_with_pdfplumber(pdf_path: Path) -> str:
    """
    Extract text from a PDF using pdfplumber.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text string (may be empty).
    """
    text_parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _extract_with_pymupdf(pdf_path: Path) -> str:
    """
    Extract text from a PDF using PyMuPDF (fitz).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text string (may be empty).
    """
    text_parts = []
    doc = fitz.open(str(pdf_path))
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts).strip()


def _extract_with_openai_vision(pdf_path: Path) -> str:
    """
    Extract text from a scanned PDF using OpenAI's vision API (gpt-4o-mini).

    Converts each PDF page to a PNG image, encodes it as base64,
    and sends it to the OpenAI vision endpoint.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text string.

    Raises:
        ValueError: If the OpenAI call fails or returns no text.
    """
    client = OpenAI(api_key=settings.openai_api_key)
    doc = fitz.open(str(pdf_path))
    all_text = []

    for page_num, page in enumerate(doc):
        # Render page as PNG image (2x DPI for clarity)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Extract all text from this government document image. "
                                    "Return only the extracted text. Preserve paragraph structure."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=4096,
            )
            page_text = response.choices[0].message.content or ""
            all_text.append(page_text.strip())
        except Exception as e:
            raise ValueError(
                f"OpenAI Vision API failed on page {page_num + 1}: {e}"
            )

    doc.close()
    return "\n\n".join(all_text).strip()


def parse_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file using a three-stage fallback strategy.

    Strategy:
    1. pdfplumber  — if output > 100 chars, return it.
    2. PyMuPDF     — if output > 100 chars, return it.
    3. OpenAI Vision API (gpt-4o-mini) — for scanned / image PDFs.

    Args:
        pdf_path: Absolute or relative path string to the PDF file.

    Returns:
        Extracted text as a string.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        ValueError: If all extraction methods fail to produce usable text.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Stage 1: pdfplumber
    try:
        text = _extract_with_pdfplumber(path)
        if len(text) > 100:
            return text
    except Exception as e:
        print(f"[pdf_parser] pdfplumber failed: {e}")

    # Stage 2: PyMuPDF
    try:
        text = _extract_with_pymupdf(path)
        if len(text) > 100:
            return text
    except Exception as e:
        print(f"[pdf_parser] PyMuPDF failed: {e}")

    # Stage 3: OpenAI Vision (scanned PDFs)
    try:
        text = _extract_with_openai_vision(path)
        if text:
            return text
    except Exception as e:
        raise ValueError(
            f"All PDF extraction methods failed for '{pdf_path}'. "
            f"Last error: {e}. "
            "Please ensure the file is a valid PDF."
        )

    raise ValueError(
        f"Could not extract readable text from '{pdf_path}'. "
        "The file may be corrupt or contain only images with no extractable text."
    )

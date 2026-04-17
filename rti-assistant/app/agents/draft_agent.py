"""
Draft Agent — generates formal RTI application letters.
Uses Groq (llama-3.3-70b-versatile) with OpenAI fallback.
"""
from datetime import date, timedelta
from typing import Dict, Optional
import re

from groq import Groq
from openai import OpenAI

from app.config import settings
from app.utils.prompt_templates import RTI_DRAFT_PROMPT
from app.utils.deadline_tracker import calculate_deadline, check_fee_waiver
from app.database.models import SessionLocal
from app.database import crud


def _call_groq(prompt: str) -> str:
    """Call the Groq API."""
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    """Call OpenAI API as fallback."""
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def _call_llm(prompt: str) -> str:
    """Call Groq; fall back to OpenAI on failure."""
    try:
        return _call_groq(prompt)
    except Exception as groq_err:
        print(f"[draft_agent] Groq failed ({groq_err}). Falling back to OpenAI...")
        try:
            return _call_openai(prompt)
        except Exception as oai_err:
            raise RuntimeError(f"Both LLMs failed. Groq: {groq_err} | OpenAI: {oai_err}")


def _enforce_letter_structure(draft_text: str, citizen_name: str, citizen_address: str, 
                               department_name: str, date_str: str) -> str:
    """Post-process LLM output to enforce strict formal RTI letter structure."""
    text = draft_text.strip()

    # Guardrail 1: Strip LLM preamble
    preamble_pattern = re.compile(
        r"^(?:here is|sure[,!]?|below is|certainly[,!]?|as requested[,!]?|the following|"
        r"please find|i have drafted|draft rti|rti application)[^\n]*\n+",
        re.IGNORECASE
    )
    text = preamble_pattern.sub("", text).lstrip()

    # Guardrail 2: Ensure letter starts with sender address
    missing_address_at_top = bool(re.match(r"^(To[,:]|Date:)", text, re.IGNORECASE))
    if missing_address_at_top:
        formatted_address = citizen_address.replace(", ", ",\n")
        text = f"{formatted_address}\n\nDate: {date_str}\n\n{text}"

    # Guardrail 3: Remove embedded address from body paragraph
    embedded_patterns = [
        r"I,?\s+" + re.escape(citizen_name) + r",?\s+residing at[^\.]+\.\s*",
        r"I,?\s+a citizen.*?residing at[^\.]+\.\s*",
        r"The applicant.*?residing at[^\.]+\.\s*",
    ]
    for pat in embedded_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)

    return text


def _sanitize_pio_block(draft_text: str, department_name: str) -> str:
    """
    Post-process LLM output to ensure PIO block uses the generic safe format.

    This function detects and replaces any hallucinated PIO names with the
    standard addressee block to ensure legally safe RTI drafts.

    Args:
        draft_text: Raw draft text from LLM.
        department_name: Name of the target department.

    Returns:
        Sanitized draft text with generic PIO addressee.
    """
    # Standard safe addressee block
    safe_pio_block = (
        f"To,\n"
        f"The Public Information Officer (PIO),\n"
        f"{department_name},\n"
        f"Government of India"
    )

    # Pattern to match various "To," blocks with potential hallucinated names
    # Matches: To, / To: followed by lines until we hit Subject: or a blank line
    pio_block_pattern = re.compile(
        r"^To[,:]?\s*\n"
        r"(?:.*?\n){1,6}?"
        r"(?=(?:Subject:|\\n\\n|Dear |Respected ))",
        re.MULTILINE | re.IGNORECASE
    )

    match = pio_block_pattern.search(draft_text)
    if match:
        # Check if the matched block contains a suspicious name pattern
        # (e.g., "Shri", "Smt", "Dr.", or capitalized names like "Rajesh Kumar")
        suspicious_patterns = [
            r"\bShri\b", r"\bSmt\.?\b", r"\bDr\.?\b", r"\bMr\.?\b", r"\bMs\.?\b",
            r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # "Rajesh Kumar" pattern
        ]
        block_text = match.group(0)
        for pattern in suspicious_patterns:
            if re.search(pattern, block_text):
                # Replace the hallucinated block with safe version
                draft_text = draft_text[:match.start()] + safe_pio_block + "\n\n" + draft_text[match.end():]
                break

    # Also ensure no "Dear [Name]" salutations with specific names
    draft_text = re.sub(
        r"Dear\s+(?:Shri|Smt\.?|Dr\.?|Mr\.?|Ms\.?)\s+[A-Z][a-z]+.*?,?",
        "Dear Sir/Madam,",
        draft_text
    )

    return draft_text


def _get_pio_details(department_name: str, db) -> Dict:
    """
    Build generic PIO details for a department.

    IMPORTANT: We intentionally do NOT use specific PIO names from the database
    to prevent hallucination and ensure legally safe RTI drafts. The addressee
    is always the generic "Public Information Officer (PIO)".

    Args:
        department_name: Name of the government department.
        db: Active SQLAlchemy session.

    Returns:
        Dict with pio_name, pio_address, pio_email, fee, dept_id.
    """
    dept = crud.get_department_by_name(db, department_name)

    # Always use generic PIO designation — never specific names
    generic_pio_name = "The Public Information Officer (PIO)"
    generic_pio_address = f"{department_name}, Government of India"

    if dept:
        return {
            "pio_name": generic_pio_name,
            "pio_address": generic_pio_address,
            "pio_email": dept.pio_email or "pio@department.gov.in",
            "fee": dept.rti_fee if hasattr(dept, "rti_fee") else 10.0,
            "dept_id": dept.id,
            "appeal_authority_name": "First Appellate Authority",
            "appeal_authority_email": dept.appeal_authority_email or "faa@department.gov.in",
        }

    # Department not in DB — still use generic format
    return {
        "pio_name": generic_pio_name,
        "pio_address": generic_pio_address,
        "pio_email": "pio@department.gov.in",
        "fee": 10.0,
        "dept_id": None,
        "appeal_authority_name": "First Appellate Authority",
        "appeal_authority_email": "faa@department.gov.in",
    }


def run_draft_agent(
    citizen_request: str,
    department_name: str,
    citizen_name: str,
    citizen_address: str,
    citizen_email: str,
    is_bpl: bool = False,
    priority: str = "NORMAL",
) -> Dict:
    """
    Generate a formal RTI application draft and save it to the database.

    Args:
        citizen_request: Plain-English description of the information needed.
        department_name: Name of the target government department.
        citizen_name: Full name of the citizen filing the RTI.
        citizen_address: Postal address of the citizen.
        citizen_email: Email address of the citizen.
        is_bpl: True if the citizen is a BPL cardholder (fee exempt).
        priority: "NORMAL" or "LIFE_LIBERTY".

    Returns:
        Dict with keys: application_id, application_number, draft_text,
        pio_name, pio_address, deadline_date, fee_amount, instructions.
    """
    db = SessionLocal()
    try:
        # Fetch PIO details
        pio = _get_pio_details(department_name, db)

        # Fee calculation
        fee_info = check_fee_waiver(is_bpl)
        fee_amount = fee_info["fee_amount"]

        # Build and call prompt (no PIO name/address - using generic format)
        today_str = date.today().strftime("%d %B %Y")
        prompt = RTI_DRAFT_PROMPT.format(
            citizen_request=citizen_request,
            department=department_name,
            citizen_name=citizen_name,
            citizen_address=citizen_address,
            date=today_str,
        )

        draft_text = _call_llm(prompt)

        # Apply format guardrails
        # 1. Sanitize any hallucinated PIO names from LLM output
        draft_text = _sanitize_pio_block(draft_text, department_name)
        
        # 2. Enforce proper letter structure (sender address at top, etc.)
        draft_text = _enforce_letter_structure(
            draft_text, citizen_name, citizen_address, department_name, today_str
        )

        # Ensure mandatory disclaimer is present
        disclaimer = "Note: This is an AI-generated draft. Please review carefully before filing."
        if disclaimer not in draft_text:
            draft_text += f"\n\n{disclaimer}"

        # Create or fetch citizen
        citizen = crud.create_citizen(
            db, citizen_name, citizen_email,
            phone="Not provided", address=citizen_address,
        )

        # Resolve department ID — create a placeholder department if missing
        dept_id = pio["dept_id"]
        if dept_id is None:
            existing_dept = crud.get_department_by_name(db, department_name)
            if existing_dept:
                dept_id = existing_dept.id
            else:
                new_dept = crud.create_department(
                    db,
                    name=department_name,
                    ministry="Government of India",
                    pio_name=pio["pio_name"],
                    pio_email=pio["pio_email"],
                    pio_address=pio["pio_address"],
                    appeal_authority_name=pio["appeal_authority_name"],
                    appeal_authority_email=pio["appeal_authority_email"],
                )
                dept_id = new_dept.id

        # Derive subject from first 120 chars of citizen request
        subject = citizen_request[:120].rstrip()

        # Save application to DB
        application = crud.create_rti_application(
            db=db,
            citizen_id=citizen.id,
            department_id=dept_id,
            subject=subject,
            information_requested=citizen_request,
            draft_text=draft_text,
            priority=priority,
            bpl_exemption=is_bpl,
        )

        deadline_str = application.deadline_date.strftime("%d %B %Y")
        instructions = (
            f"1. Review the draft carefully.\n"
            f"2. Print and sign the application.\n"
            f"3. Attach Rs. {fee_amount:.0f}/- as IPO/DD payable to the Accounts Officer.\n"
            f"4. Submit to the PIO at: {pio['pio_address']}.\n"
            f"5. Keep a copy and postal receipt. Deadline for response: {deadline_str}."
        )
        if is_bpl:
            instructions = (
                "1. Review the draft carefully.\n"
                "2. Print and sign the application.\n"
                "3. Attach a copy of your BPL card (fee exempt).\n"
                f"4. Submit to the PIO at: {pio['pio_address']}.\n"
                f"5. Keep a copy and postal receipt. Deadline for response: {deadline_str}."
            )

        return {
            "application_id": application.id,
            "application_number": application.application_number,
            "draft_text": draft_text,
            "pio_name": pio["pio_name"],
            "pio_address": pio["pio_address"],
            "deadline_date": deadline_str,
            "fee_amount": fee_amount,
            "instructions": instructions,
        }

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"[draft_agent] Failed to generate RTI draft: {e}")
    finally:
        db.close()

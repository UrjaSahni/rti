"""
API utility functions used across multiple routes.

Provides clean, reusable helpers that wrap database queries
and business logic for use in FastAPI route handlers.
"""
from datetime import date
from typing import Dict, List, Optional

from app.database.models import SessionLocal
from app.database import crud
from app.utils.deadline_tracker import (
    calculate_deadline,
    check_fee_waiver as _check_fee_waiver,
    get_days_remaining,
    is_overdue,
)


def get_pio_details(department_name: str) -> Dict:
    """
    Retrieve PIO (Public Information Officer) details for a department.

    Args:
        department_name: Name of the government department.

    Returns:
        Dict with pio_name, pio_email, pio_address, appeal_authority_name,
        appeal_authority_email, rti_fee, and found (bool).
    """
    db = SessionLocal()
    try:
        dept = crud.get_department_by_name(db, department_name)
        if dept:
            return {
                "found": True,
                "department_id": dept.id,
                "department_name": dept.name,
                "pio_name": dept.pio_name,
                "pio_email": dept.pio_email,
                "pio_address": dept.pio_address,
                "appeal_authority_name": dept.appeal_authority_name,
                "appeal_authority_email": dept.appeal_authority_email,
                "rti_fee": dept.rti_fee,
                "response_days": dept.response_days,
            }
        return {
            "found": False,
            "department_name": department_name,
            "pio_name": "The Public Information Officer",
            "pio_email": "pio@department.gov.in",
            "pio_address": f"{department_name}, Government of India",
            "appeal_authority_name": "First Appellate Authority",
            "appeal_authority_email": "faa@department.gov.in",
            "rti_fee": 10.0,
            "response_days": 30,
        }
    finally:
        db.close()


def calculate_deadline_info(filed_date: str, priority: str = "normal") -> Dict:
    """
    Calculate RTI response deadline and return a structured dict.

    Args:
        filed_date: Date the application was filed (YYYY-MM-DD format).
        priority: "normal" or "life_liberty".

    Returns:
        Dict with deadline_type, filed_date, deadline_date, days_allowed.
    """
    try:
        parsed_date = date.fromisoformat(filed_date)
    except ValueError:
        parsed_date = date.today()

    deadline_type = "life_liberty" if priority.lower() == "life_liberty" else "normal"
    deadline = calculate_deadline(parsed_date, deadline_type)
    days = (deadline - parsed_date).days

    return {
        "deadline_type": deadline_type,
        "filed_date": parsed_date.isoformat(),
        "deadline_date": deadline.isoformat(),
        "days_allowed": days,
    }


def check_fee_waiver(is_bpl: bool) -> Dict:
    """
    Check whether a BPL fee waiver applies and return fee details.

    Args:
        is_bpl: True if the citizen holds a BPL card.

    Returns:
        Dict with fee_amount (float), waiver_applied (bool), waiver_reason (str).
    """
    return _check_fee_waiver(is_bpl)


def get_appeal_authority(department_name: str) -> Dict:
    """
    Retrieve the First Appellate Authority for a department.

    Args:
        department_name: Name of the government department.

    Returns:
        Dict with appeal_authority_name, appeal_authority_email,
        appeal_deadline_days, legal_basis.
    """
    db = SessionLocal()
    try:
        dept = crud.get_department_by_name(db, department_name)
        if dept:
            return {
                "found": True,
                "appeal_authority_name": dept.appeal_authority_name,
                "appeal_authority_email": dept.appeal_authority_email,
                "appeal_deadline_days": 30,
                "legal_basis": "Section 19(1) of the Right to Information Act, 2005",
            }
        return {
            "found": False,
            "appeal_authority_name": "First Appellate Authority",
            "appeal_authority_email": "faa@department.gov.in",
            "appeal_deadline_days": 30,
            "legal_basis": "Section 19(1) of the Right to Information Act, 2005",
        }
    finally:
        db.close()


def get_application_status(application_id: int) -> Dict:
    """
    Retrieve current status information for an RTI application.

    Args:
        application_id: Primary key of the RTI application.

    Returns:
        Dict with application details and status, or error message.
    """
    db = SessionLocal()
    try:
        app = crud.get_application_by_id(db, application_id)
        if not app:
            return {"error": f"Application {application_id} not found."}

        dept = crud.get_department_by_id(db, app.department_id)
        return {
            "application_id": app.id,
            "application_number": app.application_number,
            "subject": app.subject,
            "department": dept.name if dept else "Unknown",
            "status": app.status,
            "date_filed": app.date_filed.isoformat(),
            "deadline_date": app.deadline_date.isoformat(),
            "days_remaining": get_days_remaining(app),
            "is_overdue": is_overdue(app),
        }
    finally:
        db.close()


def check_overdue_applications() -> List[Dict]:
    """
    Return a list of all overdue RTI applications.

    Returns:
        List of dicts, each containing application details.
    """
    db = SessionLocal()
    try:
        overdue = crud.get_overdue_applications(db)
        result = []
        for app in overdue:
            dept = crud.get_department_by_id(db, app.department_id)
            result.append({
                "application_id": app.id,
                "application_number": app.application_number,
                "subject": app.subject,
                "department": dept.name if dept else "Unknown",
                "date_filed": app.date_filed.isoformat(),
                "deadline_date": app.deadline_date.isoformat(),
                "days_overdue": abs(get_days_remaining(app)),
            })
        return result
    finally:
        db.close()

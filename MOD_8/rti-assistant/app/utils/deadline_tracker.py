"""
Deadline tracker utilities for RTI applications.

Implements deadline calculation, overdue detection, and status timeline
generation as per the Right to Information Act, 2005.
"""
from datetime import date, timedelta
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.database.models import RTIApplication


def calculate_deadline(filed_date: date, deadline_type: str = "normal") -> date:
    """
    Calculate the response deadline for an RTI application.

    Args:
        filed_date: The date the RTI application was filed.
        deadline_type: One of "normal", "life_liberty", "first_appeal",
                       "second_appeal", or "transfer".

    Returns:
        The calculated deadline date.

    Raises:
        ValueError: If an unknown deadline_type is provided.
    """
    mapping = {
        "normal": 30,
        "life_liberty": 2,      # 48 hours
        "first_appeal": 30,
        "second_appeal": 90,
        "transfer": 5,          # Section 6(3)
    }
    if deadline_type not in mapping:
        raise ValueError(
            f"Unknown deadline_type '{deadline_type}'. "
            f"Choose from: {list(mapping.keys())}"
        )
    return filed_date + timedelta(days=mapping[deadline_type])


def is_overdue(application: "RTIApplication") -> bool:
    """
    Determine whether an RTI application is overdue.

    An application is overdue if today is past its deadline and
    its status is not RESPONDED or RESOLVED.

    Args:
        application: RTIApplication ORM object.

    Returns:
        True if overdue, False otherwise.
    """
    if application.status in ("RESPONDED", "RESOLVED"):
        return False
    return date.today() > application.deadline_date


def get_days_remaining(application: "RTIApplication") -> int:
    """
    Return the number of days until (or since) the application deadline.

    Args:
        application: RTIApplication ORM object.

    Returns:
        Positive integer if time remains; negative if overdue.
    """
    delta = application.deadline_date - date.today()
    return delta.days


def get_status_timeline(application_id: int, db: Session) -> List[dict]:
    """
    Build an ordered event timeline for an RTI application.

    Queries the audit log and model relationships to construct a
    human-readable sequence of events.

    Args:
        application_id: Primary key of the RTI application.
        db: Active SQLAlchemy database session.

    Returns:
        List of dicts: [{"date": "YYYY-MM-DD", "event": str, "status": str}]
    """
    from app.database.models import RTIApplication, AuditLog

    app = db.query(RTIApplication).filter(
        RTIApplication.id == application_id
    ).first()

    if not app:
        return []

    timeline = []

    # Application filed event
    timeline.append({
        "date": app.date_filed.strftime("%Y-%m-%d"),
        "event": "RTI Application filed",
        "status": "SUBMITTED",
    })

    # Deadline event
    timeline.append({
        "date": app.deadline_date.strftime("%Y-%m-%d"),
        "event": "Response deadline",
        "status": "DEADLINE",
    })

    # Government response events
    for resp in app.responses:
        timeline.append({
            "date": resp.date_received.strftime("%Y-%m-%d"),
            "event": f"Government response received — {resp.response_type}",
            "status": "RESPONDED",
        })

    # Appeal events
    for appeal in app.appeals:
        timeline.append({
            "date": appeal.date_filed.strftime("%Y-%m-%d"),
            "event": f"{appeal.appeal_type} Appeal filed",
            "status": "APPEALED",
        })

    # Audit log events (excluding auto-generated ones)
    audit_entries = db.query(AuditLog).filter(
        AuditLog.application_id == application_id,
        AuditLog.performed_by != "system",
    ).order_by(AuditLog.timestamp).all()

    for entry in audit_entries:
        timeline.append({
            "date": entry.timestamp.strftime("%Y-%m-%d"),
            "event": entry.action,
            "status": app.status,
        })

    # Sort by date
    timeline.sort(key=lambda x: x["date"])
    return timeline


def check_fee_waiver(is_bpl: bool) -> dict:
    """
    Determine the RTI application fee and whether a waiver applies.

    Citizens below the poverty line (BPL) are exempt from the Rs. 10 fee
    as per Rule 3 of the Right to Information (Regulation of Fee and Cost)
    Rules, 2005.

    Args:
        is_bpl: True if the citizen is a BPL cardholder.

    Returns:
        dict with keys: fee_amount (float), waiver_applied (bool),
        waiver_reason (str).
    """
    if is_bpl:
        return {
            "fee_amount": 0.0,
            "waiver_applied": True,
            "waiver_reason": (
                "BPL exemption applies under Rule 3 of the RTI "
                "(Regulation of Fee and Cost) Rules, 2005."
            ),
        }
    return {
        "fee_amount": 10.0,
        "waiver_applied": False,
        "waiver_reason": "Standard fee of Rs. 10/- applies.",
    }

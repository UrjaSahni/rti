"""
CRUD operations for all database models.

Provides functions to create, read, update, and delete records
in a clean, reusable way that wraps SQLAlchemy sessions.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.database.models import (
    AuditLog, Appeal, Citizen, Department,
    GovernmentResponse, RTIApplication,
)


# ─────────────────────────────────────────────
# Citizen CRUD
# ─────────────────────────────────────────────

def get_citizen_by_email(db: Session, email: str) -> Optional[Citizen]:
    """Retrieve a citizen record by email address (case-insensitive)."""
    return db.query(Citizen).filter(Citizen.email.ilike(email.strip())).first()


def get_top_citizens_by_apps(db: Session, limit: int = 10):
    """Return top citizens ordered by number of RTI applications filed."""
    from sqlalchemy import func
    return (
        db.query(Citizen.email, func.count(RTIApplication.id).label("app_count"))
        .join(RTIApplication, RTIApplication.citizen_id == Citizen.id)
        .group_by(Citizen.id)
        .order_by(func.count(RTIApplication.id).desc())
        .limit(limit)
        .all()
    )


def get_citizen_by_id(db: Session, citizen_id: int) -> Optional[Citizen]:
    """
    Retrieve a citizen record by primary key.

    Args:
        db: Active database session.
        citizen_id: Citizen's primary key.

    Returns:
        Citizen object if found, else None.
    """
    return db.query(Citizen).filter(Citizen.id == citizen_id).first()


def create_citizen(db: Session, name: str, email: str, phone: str, address: str) -> Citizen:
    """
    Create a new citizen record, or return existing if email already exists.

    Args:
        db: Active database session.
        name: Citizen's full name.
        email: Citizen's email address.
        phone: Citizen's phone number.
        address: Citizen's postal address.

    Returns:
        Newly created or existing Citizen object.
    """
    existing = get_citizen_by_email(db, email)
    if existing:
        return existing
    citizen = Citizen(name=name, email=email, phone=phone, address=address)
    db.add(citizen)
    db.commit()
    db.refresh(citizen)
    return citizen


# ─────────────────────────────────────────────
# Department CRUD
# ─────────────────────────────────────────────

def get_all_departments(db: Session) -> List[Department]:
    """
    Return all department records.

    Args:
        db: Active database session.

    Returns:
        List of Department objects.
    """
    return db.query(Department).all()


def get_department_by_name(db: Session, name: str) -> Optional[Department]:
    """
    Retrieve a department by name (case-insensitive partial match).

    Args:
        db: Active database session.
        name: Department name or partial name.

    Returns:
        Department object if found, else None.
    """
    return db.query(Department).filter(
        Department.name.ilike(f"%{name}%")
    ).first()


def get_department_by_id(db: Session, dept_id: int) -> Optional[Department]:
    """
    Retrieve a department by primary key.

    Args:
        db: Active database session.
        dept_id: Department primary key.

    Returns:
        Department object if found, else None.
    """
    return db.query(Department).filter(Department.id == dept_id).first()


def create_department(db: Session, **kwargs) -> Department:
    """
    Create a new department record.

    Args:
        db: Active database session.
        **kwargs: Department field values.

    Returns:
        Newly created Department object.
    """
    dept = Department(**kwargs)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


# ─────────────────────────────────────────────
# RTI Application CRUD
# ─────────────────────────────────────────────

def generate_application_number() -> str:
    """
    Generate a unique RTI application number in format RTI/YYYY/XXXXX.

    Returns:
        Application number string.
    """
    import random
    year = datetime.now().year
    seq = random.randint(10000, 99999)
    return f"RTI/{year}/{seq}"


def create_rti_application(
    db: Session,
    citizen_id: int,
    department_id: int,
    subject: str,
    information_requested: str,
    draft_text: str,
    priority: str = "NORMAL",
    bpl_exemption: bool = False,
) -> RTIApplication:
    """
    Create a new RTI application with auto-calculated deadline.

    Args:
        db: Active database session.
        citizen_id: ID of the filing citizen.
        department_id: ID of the target department.
        subject: Subject line of the RTI application.
        information_requested: Full information request text.
        draft_text: Generated RTI letter text.
        priority: NORMAL or LIFE_LIBERTY.
        bpl_exemption: Whether BPL fee exemption applies.

    Returns:
        Newly created RTIApplication object.
    """
    today = date.today()
    days = 2 if priority == "LIFE_LIBERTY" else 30
    deadline = today + timedelta(days=days)
    fee = 0.0 if bpl_exemption else 10.0

    app_number = generate_application_number()
    # Ensure uniqueness
    while db.query(RTIApplication).filter(
        RTIApplication.application_number == app_number
    ).first():
        app_number = generate_application_number()

    application = RTIApplication(
        application_number=app_number,
        citizen_id=citizen_id,
        department_id=department_id,
        subject=subject,
        information_requested=information_requested,
        date_filed=today,
        deadline_date=deadline,
        status="DRAFT",
        priority=priority,
        fee_paid=False,
        fee_amount=fee,
        bpl_exemption=bpl_exemption,
        draft_text=draft_text,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    log_audit(db, application.id, "Application created", "system")
    return application


def get_application_by_id(db: Session, app_id: int) -> Optional[RTIApplication]:
    """
    Retrieve an RTI application by primary key.

    Args:
        db: Active database session.
        app_id: Application primary key.

    Returns:
        RTIApplication object if found, else None.
    """
    return db.query(RTIApplication).filter(RTIApplication.id == app_id).first()


def get_applications_by_citizen_email(db: Session, email: str) -> List[RTIApplication]:
    """
    Retrieve all RTI applications filed by a citizen (by email).

    Args:
        db: Active database session.
        email: Citizen's email address.

    Returns:
        List of RTIApplication objects.
    """
    citizen = get_citizen_by_email(db, email)
    if not citizen:
        return []
    return db.query(RTIApplication).filter(
        RTIApplication.citizen_id == citizen.id
    ).order_by(RTIApplication.date_filed.desc()).all()


def update_application_status(db: Session, app_id: int, status: str) -> Optional[RTIApplication]:
    """
    Update the status of an RTI application.

    Args:
        db: Active database session.
        app_id: Application primary key.
        status: New status string.

    Returns:
        Updated RTIApplication object if found, else None.
    """
    app = get_application_by_id(db, app_id)
    if app:
        app.status = status
        app.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(app)
        log_audit(db, app_id, f"Status updated to {status}", "system")
    return app


def get_overdue_applications(db: Session) -> List[RTIApplication]:
    """
    Return all applications past their deadline and not resolved.

    Args:
        db: Active database session.

    Returns:
        List of overdue RTIApplication objects.
    """
    today = date.today()
    return db.query(RTIApplication).filter(
        RTIApplication.deadline_date < today,
        RTIApplication.status.notin_(["RESPONDED", "RESOLVED"])
    ).all()


# ─────────────────────────────────────────────
# Government Response CRUD
# ─────────────────────────────────────────────

def create_government_response(
    db: Session,
    application_id: int,
    response_type: str,
    response_text: str,
    pdf_path: Optional[str] = None,
    confidence: float = 0.0,
    summary: str = "",
) -> GovernmentResponse:
    """
    Create a government response record for an RTI application.

    Args:
        db: Active database session.
        application_id: ID of the related RTI application.
        response_type: Classification (FULL/PARTIAL/DENIED/TRANSFERRED/NO_RESPONSE).
        response_text: Full text of the response.
        pdf_path: Optional path to the PDF file.
        confidence: Classification confidence score.
        summary: Short summary of the response.

    Returns:
        Newly created GovernmentResponse object.
    """
    response = GovernmentResponse(
        application_id=application_id,
        date_received=date.today(),
        response_type=response_type,
        response_text=response_text,
        pdf_path=pdf_path,
        classification_confidence=confidence,
        classified_by="model",
        summary=summary,
    )
    db.add(response)
    db.commit()
    db.refresh(response)

    # Map response type to application status
    status_map = {
        "FULL": "RESPONDED",
        "PARTIAL": "RESPONDED",
        "DENIED": "RESPONDED",
        "TRANSFERRED": "RESPONDED",
        "NO_RESPONSE": "OVERDUE",
    }
    new_status = status_map.get(response_type, "RESPONDED")
    update_application_status(db, application_id, new_status)
    log_audit(db, application_id, f"Response classified as {response_type}", "system")
    return response


def get_latest_response(db: Session, application_id: int) -> Optional[GovernmentResponse]:
    """
    Retrieve the most recent government response for an application.

    Args:
        db: Active database session.
        application_id: RTI application primary key.

    Returns:
        Latest GovernmentResponse object if found, else None.
    """
    return db.query(GovernmentResponse).filter(
        GovernmentResponse.application_id == application_id
    ).order_by(GovernmentResponse.id.desc()).first()


# ─────────────────────────────────────────────
# Appeal CRUD
# ─────────────────────────────────────────────

def create_appeal(
    db: Session,
    application_id: int,
    appeal_type: str,
    grounds: str,
    draft_text: str,
) -> Appeal:
    """
    Create an appeal record for an RTI application.

    Args:
        db: Active database session.
        application_id: ID of the related RTI application.
        appeal_type: FIRST or SECOND.
        grounds: Legal grounds for the appeal.
        draft_text: Full text of the appeal letter.

    Returns:
        Newly created Appeal object.
    """
    appeal = Appeal(
        application_id=application_id,
        appeal_type=appeal_type,
        date_filed=date.today(),
        grounds=grounds,
        draft_text=draft_text,
        status="FILED",
    )
    db.add(appeal)
    db.commit()
    db.refresh(appeal)
    update_application_status(db, application_id, "APPEALED")
    log_audit(db, application_id, f"{appeal_type} appeal filed", "citizen")
    return appeal


def get_appeals_by_application(db: Session, application_id: int) -> List[Appeal]:
    """
    Retrieve all appeals for a given RTI application.

    Args:
        db: Active database session.
        application_id: RTI application primary key.

    Returns:
        List of Appeal objects ordered by date filed.
    """
    return db.query(Appeal).filter(
        Appeal.application_id == application_id
    ).order_by(Appeal.date_filed).all()


# ─────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────

def log_audit(
    db: Session,
    application_id: Optional[int],
    action: str,
    performed_by: str = "system",
    notes: str = "",
) -> AuditLog:
    """
    Append an entry to the audit log.

    Args:
        db: Active database session.
        application_id: Related RTI application ID (can be None for system events).
        action: Description of the action.
        performed_by: Actor who performed the action.
        notes: Additional notes.

    Returns:
        Newly created AuditLog object.
    """
    entry = AuditLog(
        application_id=application_id,
        action=action,
        performed_by=performed_by,
        timestamp=datetime.utcnow(),
        notes=notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

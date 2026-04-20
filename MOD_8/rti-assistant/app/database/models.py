"""
SQLAlchemy ORM models for the RTI Query Assistant.

Defines all database tables: Citizen, Department, RTIApplication,
GovernmentResponse, Appeal, AuditLog.
"""
from datetime import datetime, date
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from app.config import settings

Base = declarative_base()


def get_engine():
    """Create and return the SQLAlchemy engine using DATABASE_URL from settings."""
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    )


def get_session_local():
    """Return a configured SessionLocal class."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


SessionLocal = get_session_local()


def get_db():
    """
    FastAPI dependency that yields a database session.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables if they do not already exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


class Citizen(Base):
    """Represents a citizen who files RTI applications.

    Attributes:
        id: Primary key.
        name: Full name of the citizen.
        email: Unique email address.
        phone: Contact number.
        address: Postal address.
        created_at: Timestamp when the record was created.
    """

    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    applications = relationship("RTIApplication", back_populates="citizen")


class Department(Base):
    """Represents a government department / public authority.

    Attributes:
        id: Primary key.
        name: Department name.
        ministry: Parent ministry name.
        pio_name: Name of the Public Information Officer.
        pio_email: PIO email address.
        pio_address: PIO postal address.
        appeal_authority_name: Name of the First Appellate Authority.
        appeal_authority_email: FAA email address.
        rti_fee: Application fee in rupees (default 10.0).
        response_days: Days allowed for response (default 30).
        is_central_govt: Whether it is a central government body.
    """

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    ministry = Column(String(255), nullable=False)
    pio_name = Column(String(255), nullable=False)
    pio_email = Column(String(255), nullable=False)
    pio_address = Column(Text, nullable=False)
    appeal_authority_name = Column(String(255), nullable=False)
    appeal_authority_email = Column(String(255), nullable=False)
    rti_fee = Column(Float, default=10.0)
    response_days = Column(Integer, default=30)
    is_central_govt = Column(Boolean, default=True)

    applications = relationship("RTIApplication", back_populates="department")


class RTIApplication(Base):
    """Represents an RTI application filed by a citizen.

    Attributes:
        id: Primary key.
        application_number: Unique application number (RTI/YYYY/XXXXX).
        citizen_id: Foreign key to citizens table.
        department_id: Foreign key to departments table.
        subject: Subject line of the RTI application.
        information_requested: Full text of information requested.
        date_filed: Date the application was filed.
        deadline_date: Date by which response is required (date_filed + 30 days).
        status: Application status (DRAFT/SUBMITTED/RESPONDED/APPEALED/RESOLVED/OVERDUE).
        priority: Priority level (NORMAL/LIFE_LIBERTY).
        fee_paid: Whether the RTI fee has been paid.
        fee_amount: Fee amount in rupees.
        bpl_exemption: Whether BPL fee exemption applies.
        draft_text: Full text of the RTI application draft.
        created_at: Timestamp when record was created.
        updated_at: Timestamp when record was last updated.
    """

    __tablename__ = "rti_applications"

    id = Column(Integer, primary_key=True, index=True)
    application_number = Column(String(50), unique=True, nullable=False, index=True)
    citizen_id = Column(Integer, ForeignKey("citizens.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    subject = Column(String(500), nullable=False)
    information_requested = Column(Text, nullable=False)
    date_filed = Column(Date, nullable=False, default=date.today)
    deadline_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT")
    priority = Column(String(20), nullable=False, default="NORMAL")
    fee_paid = Column(Boolean, default=False)
    fee_amount = Column(Float, default=10.0)
    bpl_exemption = Column(Boolean, default=False)
    draft_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    citizen = relationship("Citizen", back_populates="applications")
    department = relationship("Department", back_populates="applications")
    responses = relationship("GovernmentResponse", back_populates="application")
    appeals = relationship("Appeal", back_populates="application")
    audit_logs = relationship("AuditLog", back_populates="application")


class GovernmentResponse(Base):
    """Represents a government department's response to an RTI application.

    Attributes:
        id: Primary key.
        application_id: Foreign key to rti_applications.
        date_received: Date the response was received.
        response_type: Classification (FULL/PARTIAL/DENIED/TRANSFERRED/NO_RESPONSE).
        response_text: Full text of the response.
        pdf_path: Path to the uploaded PDF response.
        classification_confidence: Model confidence score (0.0–1.0).
        classified_by: Who classified the response (human/model).
        summary: Short summary of the response.
    """

    __tablename__ = "government_responses"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("rti_applications.id"), nullable=False)
    date_received = Column(Date, nullable=False, default=date.today)
    response_type = Column(String(20), nullable=False, default="NO_RESPONSE")
    response_text = Column(Text, nullable=True)
    pdf_path = Column(String(500), nullable=True)
    classification_confidence = Column(Float, default=0.0)
    classified_by = Column(String(20), default="model")
    summary = Column(Text, nullable=True)

    application = relationship("RTIApplication", back_populates="responses")


class Appeal(Base):
    """Represents an appeal filed against an RTI decision.

    Attributes:
        id: Primary key.
        application_id: Foreign key to rti_applications.
        appeal_type: Type of appeal (FIRST/SECOND).
        date_filed: Date the appeal was filed.
        grounds: Grounds for the appeal.
        draft_text: Full text of the appeal letter.
        status: Current status of the appeal.
        outcome: Outcome of the appeal (if decided).
    """

    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("rti_applications.id"), nullable=False)
    appeal_type = Column(String(10), nullable=False, default="FIRST")
    date_filed = Column(Date, nullable=False, default=date.today)
    grounds = Column(Text, nullable=True)
    draft_text = Column(Text, nullable=True)
    status = Column(String(50), default="FILED")
    outcome = Column(String(500), nullable=True)

    application = relationship("RTIApplication", back_populates="appeals")


class AuditLog(Base):
    """Audit trail for all actions on RTI applications.

    Attributes:
        id: Primary key.
        application_id: Foreign key to rti_applications.
        action: Description of the action performed.
        performed_by: Who performed the action.
        timestamp: When the action occurred.
        notes: Additional notes.
    """

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("rti_applications.id"), nullable=True)
    action = Column(String(500), nullable=False)
    performed_by = Column(String(255), default="system")
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    application = relationship("RTIApplication", back_populates="audit_logs")

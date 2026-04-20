"""
Pydantic schemas for request/response validation in the RTI API.
"""
from datetime import date, datetime
from typing import List, Optional
import re
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────
# Citizen Schemas
# ─────────────────────────────────────────────

class CitizenBase(BaseModel):
    """Base schema for citizen data."""
    name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., max_length=255)
    phone: str = Field(..., max_length=20)
    address: str

    @field_validator('name')
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Remove potentially harmful characters from name."""
        return re.sub(r'[<>{}[\]\\]', '', v.strip())

    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Basic email format validation."""
        v = v.strip().lower()
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('Invalid email format')
        return v


class CitizenCreate(CitizenBase):
    """Schema for creating a new citizen record."""
    pass


class CitizenOut(CitizenBase):
    """Schema for returning citizen data."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# Department Schemas
# ─────────────────────────────────────────────

class DepartmentBase(BaseModel):
    """Base schema for department data."""
    name: str
    ministry: str
    pio_name: str
    pio_email: str
    pio_address: str
    appeal_authority_name: str
    appeal_authority_email: str
    rti_fee: float = 10.0
    response_days: int = 30
    is_central_govt: bool = True


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new department."""
    pass


class DepartmentOut(DepartmentBase):
    """Schema for returning department data."""
    id: int

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# RTI Application Schemas
# ─────────────────────────────────────────────

class RTIDraftRequest(BaseModel):
    """Request schema for drafting a new RTI application."""
    citizen_request: str = Field(..., min_length=10, max_length=5000, description="Plain English description of the information needed")
    department_name: str = Field(..., min_length=3, max_length=255, description="Name of the government department")
    citizen_name: str = Field(..., min_length=2, max_length=255)
    citizen_address: str = Field(..., min_length=10, max_length=1000)
    citizen_email: str = Field(..., max_length=255)
    is_bpl: bool = False

    @field_validator('citizen_request')
    @classmethod
    def sanitize_request(cls, v: str) -> str:
        """Sanitize citizen request input."""
        v = re.sub(r'[<>{}[\]\\]', '', v.strip())
        if len(v) < 10:
            raise ValueError('Request must be at least 10 characters')
        return v

    @field_validator('citizen_name')
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Remove harmful characters from name."""
        return re.sub(r'[<>{}[\]\\]', '', v.strip())

    @field_validator('citizen_email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format."""
        v = v.strip().lower()
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('Invalid email format')
        return v


class RTIApplicationBase(BaseModel):
    """Base schema for RTI application data."""
    subject: str
    information_requested: str
    date_filed: date
    deadline_date: date
    status: str
    priority: str
    fee_paid: bool
    fee_amount: float
    bpl_exemption: bool
    draft_text: Optional[str] = None


class RTIApplicationCreate(RTIApplicationBase):
    """Schema for creating an RTI application."""
    application_number: str
    citizen_id: int
    department_id: int


class RTIApplicationOut(RTIApplicationBase):
    """Schema for returning RTI application data."""
    id: int
    application_number: str
    citizen_id: int
    department_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RTIDraftResponse(BaseModel):
    """Response schema for a generated RTI draft."""
    application_id: int
    application_number: str
    draft_text: str
    pio_name: str
    pio_address: str
    deadline_date: str
    fee_amount: float
    instructions: str
    department_suggestion: Optional[dict] = None  # dept auto-correct result


# ─────────────────────────────────────────────
# Department Auto-Correct Schemas
# ─────────────────────────────────────────────

class DeptCheckRequest(BaseModel):
    """Request schema for department auto-correction check."""
    query: str = Field(..., min_length=5, max_length=5000,
                       description="The citizen's information request")
    selected_department: str = Field(..., min_length=2, max_length=255,
                                     description="Department chosen by the user")

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        return re.sub(r'[<>{}[\]\\]', '', v.strip())


class DeptSuggestion(BaseModel):
    """A single department suggestion with score."""
    department: str
    score: float


class DeptCheckResponse(BaseModel):
    """Response schema for department auto-correction."""
    corrected: bool
    suggested_department: str
    top_suggestions: List[DeptSuggestion]
    confidence: float
    message: str


# ─────────────────────────────────────────────
# Government Response Schemas
# ─────────────────────────────────────────────

class ResponseParseRequest(BaseModel):
    """Request schema for parsing a government response."""
    application_id: int
    response_text: Optional[str] = None


class GovernmentResponseOut(BaseModel):
    """Schema for returning parsed government response data."""
    id: int
    application_id: int
    date_received: date
    response_type: str
    response_text: Optional[str]
    classification_confidence: float
    summary: Optional[str]

    class Config:
        from_attributes = True


class ClassificationResult(BaseModel):
    """Schema for response classification result."""
    classification: str
    confidence: float
    summary: str
    recommended_action: str
    raw_text: str = Field(..., description="Original response text for appeal generation")


# ─────────────────────────────────────────────
# Appeal Schemas
# ─────────────────────────────────────────────

class AppealRequest(BaseModel):
    """Request schema for drafting an appeal."""
    # response_text can be empty for NO_RESPONSE cases (deemed refusal)
    response_text: str = Field(
        default="",
        max_length=10000,
        description="The government response text (can be empty for NO_RESPONSE)"
    )
    classification: str = Field(
        ...,
        description="Response classification: DENIED, PARTIAL, NO_RESPONSE, TRANSFERRED, ALLOWED, REJECTED"
    )
    
    appellant_name: Optional[str] = Field(None, max_length=255, description="Appellant's name (defaults to [Your Name])")
    appellant_address: Optional[str] = Field(None, max_length=1000, description="Appellant's address (defaults to [Your Address])")
    department_name: Optional[str] = Field(None, max_length=255, description="Department name (defaults to [Department Name])")
    rti_subject: Optional[str] = Field(None, max_length=500, description="Subject of original RTI (defaults to generic)")
    date_filed: Optional[str] = Field(None, max_length=50, description="Date RTI was filed (defaults to [Date of RTI Filing])")

    @field_validator('classification')
    @classmethod
    def validate_classification(cls, v: str) -> str:
        """Ensure classification is valid."""
        valid = {'DENIED', 'PARTIAL', 'NO_RESPONSE', 'TRANSFERRED', 'ALLOWED', 'REJECTED'}
        v = v.upper().strip()
        if v not in valid:
            raise ValueError(f'Classification must be one of: {", ".join(sorted(valid))}')
        return v

    @field_validator('response_text')
    @classmethod
    def sanitize_response_text(cls, v: str) -> str:
        """Sanitize response text (allow empty for NO_RESPONSE)."""
        if not v:
            return ""
        return re.sub(r'[<>{}[\]\\]', '', v.strip())


class AppealOut(BaseModel):
    """
    Schema for returning an appeal draft (conditional output).
    
    Output varies based on classification:
    - ALLOWED: type="no_appeal", message=..., suggestion=...
    - PARTIAL/NO_RESPONSE/REJECTED/DENIED: type="appeal_letter", content=...
    """
    # Type indicator: "no_appeal", "appeal_letter", or "error"
    type: str
    
    # For "no_appeal" type (ALLOWED classification)
    message: Optional[str] = None
    suggestion: Optional[str] = None
    
    # For "appeal_letter" type (PARTIAL/NO_RESPONSE/REJECTED/DENIED)
    content: Optional[str] = None
    classification: Optional[str] = None
    grounds_summary: Optional[str] = None
    
    # Common fields
    legal_reference: Optional[str] = None
    deadline: Optional[str] = None
    
    # Legacy fields for backward compatibility
    appeal_text: Optional[str] = None
    grounds: Optional[str] = None
    appeal_authority: Optional[str] = None
    deadline_to_file: Optional[str] = None
    legal_basis: Optional[str] = None


# ─────────────────────────────────────────────
# Rights / RAG Schemas
# ─────────────────────────────────────────────

class RightsRequest(BaseModel):
    """Request schema for the rights Q&A endpoint."""
    question: str = Field(..., min_length=5, max_length=2000)

    @field_validator('question')
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        """Sanitize question input."""
        return re.sub(r'[<>{}[\]\\]', '', v.strip())


class RightsResponse(BaseModel):
    """Response schema for the rights Q&A endpoint."""
    answer: str
    source_sections: List[str]
    case_precedents: List[str]
    confidence: float


# ─────────────────────────────────────────────
# Tracking Schemas
# ─────────────────────────────────────────────

class TimelineEvent(BaseModel):
    """A single event in the RTI application timeline."""
    date: str
    event: str
    status: str


class TrackingResponse(BaseModel):
    """Response schema for application tracking."""
    application_number: str
    subject: str
    department: str
    status: str
    date_filed: str
    deadline_date: str
    days_remaining: int
    is_overdue: bool
    timeline: List[TimelineEvent]


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    """API health check response."""
    status: str
    chroma_ready: bool
    db_ready: bool

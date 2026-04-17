"""
RTI Application routes — draft, track, list applications.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import get_db
from app.database import crud
from app.database.schemas import (
    RTIDraftRequest, RTIDraftResponse, TrackingResponse, TimelineEvent,
    DeptCheckRequest, DeptCheckResponse,
)
from app.agents.draft_agent import run_draft_agent
from app.utils.deadline_tracker import get_days_remaining, is_overdue, get_status_timeline
from app.utils.dept_corrector import auto_correct_department
from app.utils.input_validator import is_valid_query

router = APIRouter()


@router.post("/check-department", response_model=DeptCheckResponse)
async def check_department(request: DeptCheckRequest):
    """
    Check whether the selected department matches the query.

    Runs keyword + TF-IDF analysis and returns a correction suggestion
    if the selected department appears to be wrong.
    """
    result = auto_correct_department(request.query, request.selected_department)
    return DeptCheckResponse(**result)


@router.post("/draft-rti", response_model=RTIDraftResponse)
async def draft_rti(request: RTIDraftRequest, db: Session = Depends(get_db)):
    """
    Generate a formal RTI application draft.

    Auto-corrects the department if the query signals a mismatch, then
    calls the draft agent and returns the generated letter with metadata.
    """
    # Validate input before calling LLM
    is_valid, error_message = is_valid_query(request.citizen_request)
    if not is_valid:
        return RTIDraftResponse(
            draft_text=f"⚠️ {error_message}\n\nPlease describe what information you need from the government in clear, specific terms.",
            department_name=request.department_name,
            fee_required=10.00,
            department_suggestion={
                "corrected": False,
                "selected_department": request.department_name,
                "suggested_department": request.department_name,
                "confidence": 0.0,
                "message": "",
            },
        )
    
    # Auto-correct department before drafting
    dept_suggestion = auto_correct_department(request.citizen_request, request.department_name)
    effective_dept = (
        dept_suggestion["suggested_department"]
        if dept_suggestion["corrected"]
        else request.department_name
    )

    try:
        result = run_draft_agent(
            citizen_request=request.citizen_request,
            department_name=effective_dept,
            citizen_name=request.citizen_name,
            citizen_address=request.citizen_address,
            citizen_email=request.citizen_email,
            is_bpl=request.is_bpl,
        )
        result["department_suggestion"] = dept_suggestion
        return RTIDraftResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track/{application_id}", response_model=TrackingResponse)
async def track_application(application_id: int, db: Session = Depends(get_db)):
    """
    Track the status and deadline of an RTI application.

    Args:
        application_id: Primary key of the RTI application.
        db: Database session (injected).

    Returns:
        TrackingResponse with status, deadline, days remaining, and timeline.
    """
    app = crud.get_application_by_id(db, application_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found.")

    dept = crud.get_department_by_id(db, app.department_id)
    timeline_raw = get_status_timeline(application_id, db)
    timeline = [TimelineEvent(**t) for t in timeline_raw]

    return TrackingResponse(
        application_number=app.application_number,
        subject=app.subject,
        department=dept.name if dept else "Unknown",
        status=app.status,
        date_filed=app.date_filed.strftime("%Y-%m-%d"),
        deadline_date=app.deadline_date.strftime("%Y-%m-%d"),
        days_remaining=get_days_remaining(app),
        is_overdue=is_overdue(app),
        timeline=timeline,
    )


@router.get("/applications/{citizen_email}")
async def get_citizen_applications(citizen_email: str, db: Session = Depends(get_db)):
    """
    Retrieve all RTI applications filed by a citizen.

    Args:
        citizen_email: Email address of the citizen.
        db: Database session (injected).

    Returns:
        List of application summaries.
    """
    applications = crud.get_applications_by_citizen_email(db, citizen_email)
    if not applications:
        return []

    result = []
    for app in applications:
        dept = crud.get_department_by_id(db, app.department_id)
        result.append({
            "application_id": app.id,
            "application_number": app.application_number,
            "subject": app.subject,
            "department": dept.name if dept else "Unknown",
            "status": app.status,
            "date_filed": app.date_filed.strftime("%Y-%m-%d"),
            "deadline_date": app.deadline_date.strftime("%Y-%m-%d"),
            "days_remaining": get_days_remaining(app),
            "is_overdue": is_overdue(app),
        })
    return result


@router.get("/departments")
async def list_departments(db: Session = Depends(get_db)):
    """List all departments with PIO details."""
    departments = crud.get_all_departments(db)
    return [
        {
            "id": d.id,
            "name": d.name,
            "ministry": d.ministry,
            "pio_name": d.pio_name,
            "pio_email": d.pio_email,
            "pio_address": d.pio_address,
            "appeal_authority_name": d.appeal_authority_name,
            "rti_fee": d.rti_fee,
            "response_days": d.response_days,
        }
        for d in departments
    ]


@router.get("/top-filers")
async def top_filers(limit: int = 10, db: Session = Depends(get_db)):
    """Return top citizen emails by number of RTI applications filed."""
    rows = crud.get_top_citizens_by_apps(db, limit=limit)
    return [{"email": r.email, "app_count": r.app_count} for r in rows]

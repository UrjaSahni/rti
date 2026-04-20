"""
Appeal drafting route — generates a first appeal letter under Section 19(1).

REFACTORED: No database dependency. Takes response_text + classification directly.
"""
from fastapi import APIRouter, HTTPException

from app.database.schemas import AppealRequest, AppealOut
from app.agents.appeal_agent import run_appeal_agent
from app.utils.input_validator import is_valid_query

router = APIRouter()


@router.post("/draft-appeal", response_model=AppealOut)
async def draft_appeal(request: AppealRequest):
    """
    Draft a first appeal letter based on response classification.

    NO DATABASE DEPENDENCY — all data provided in the request body.
    User uploads/pastes response → gets classification → clicks Generate Appeal.

    Args:
        request: AppealRequest with response_text, classification, and optional
                 personal details (appellant_name, appellant_address, etc.).

    Returns:
        AppealOut with appeal_text, grounds, appeal_authority,
        deadline_to_file, and legal_basis.
    """
    # Validate input - skip validation for NO_RESPONSE (deemed refusal) cases
    if request.classification != "NO_RESPONSE" and request.response_text:
        is_valid, error_message = is_valid_query(request.response_text)
        if not is_valid:
            return AppealOut(
                type="error",
                message=f"⚠️ {error_message}",
                content=None,
                legal_reference="Please provide valid government response text to generate an appeal.",
            )
    
    try:
        result = run_appeal_agent(
            response_text=request.response_text,
            classification=request.classification,
            appellant_name=request.appellant_name,
            appellant_address=request.appellant_address,
            department_name=request.department_name,
            rti_subject=request.rti_subject,
            date_filed=request.date_filed,
        )
        return AppealOut(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

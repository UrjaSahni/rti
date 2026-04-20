"""
Rights Q&A routes — answer RTI rights questions using RAG.
"""
from fastapi import APIRouter, HTTPException

from app.database.schemas import RightsRequest, RightsResponse
from app.agents.rag_agent import run_rag_agent
from app.utils.input_validator import is_valid_query

router = APIRouter()


@router.post("/check-rights", response_model=RightsResponse)
async def check_rights(request: RightsRequest):
    """
    Answer an RTI rights question using the RAG agent.

    Retrieves context from the RTI Act 2005 and CIC case precedents,
    then uses an LLM to generate a grounded, section-cited answer.

    Args:
        request: RightsRequest with the citizen's question.

    Returns:
        RightsResponse with answer, cited sections, case precedents, and confidence.
    """
    # Validate input before calling LLM
    is_valid, error_message = is_valid_query(request.question)
    if not is_valid:
        return RightsResponse(
            answer=f"⚠️ {error_message}",
            source_sections=[],
            case_precedents=[],
            confidence=0.0,
        )
    
    try:
        result = run_rag_agent(request.question)
        return RightsResponse(
            answer=result["answer"],
            source_sections=result.get("source_sections", []),
            case_precedents=result.get("case_precedents", []),
            confidence=result.get("confidence", 0.5),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
LangGraph Orchestrator — routes user inputs to the appropriate agent.
"""
from typing import Any, Dict, Optional, TypedDict
import re

from groq import Groq
from openai import OpenAI
from langgraph.graph import StateGraph, END

from app.config import settings
from app.utils.prompt_templates import INTENT_CLASSIFIER_PROMPT
from app.agents.draft_agent import run_draft_agent
from app.agents.rag_agent import run_rag_agent
from app.agents.response_agent import run_response_agent
from app.agents.appeal_agent import run_appeal_agent
from app.database.models import SessionLocal
from app.database import crud
from app.utils.deadline_tracker import is_overdue, get_days_remaining, get_status_timeline


# ─── Input Validation Guardrails ───────────────────────────────────────────────

MAX_INPUT_LENGTH = 10000
MIN_INPUT_LENGTH = 3

def _validate_input(text: str) -> tuple[bool, str]:
    """
    Validate user input for safety and sanity.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text or not text.strip():
        return False, "Input cannot be empty."
    
    text = text.strip()
    
    if len(text) < MIN_INPUT_LENGTH:
        return False, f"Input too short (minimum {MIN_INPUT_LENGTH} characters)."
    
    if len(text) > MAX_INPUT_LENGTH:
        return False, f"Input too long (maximum {MAX_INPUT_LENGTH} characters)."
    
    # Check for potential injection patterns
    suspicious_patterns = [
        r'<script', r'javascript:', r'eval\(', r'exec\(',
        r'\{\{', r'\}\}', r'\$\{', r'<%', r'%>'
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Input contains invalid characters."
    
    return True, ""


def _sanitize_input(text: str) -> str:
    """Sanitize input by removing potentially harmful characters."""
    text = re.sub(r'[<>{}[\]\\]', '', text.strip())
    return text[:MAX_INPUT_LENGTH]


# ─── State Schema ──────────────────────────────────────────────────────────────

class RTIState(TypedDict, total=False):
    """Shared state passed between all nodes in the orchestrator graph."""
    user_input: str
    intent: str
    context: Dict[str, Any]
    draft_result: Dict[str, Any]
    rag_result: Dict[str, Any]
    response_result: Dict[str, Any]
    appeal_result: Dict[str, Any]
    final_response: Dict[str, Any]
    error: str


# ─── Intent Classifier ─────────────────────────────────────────────────────────

def _keyword_intent(text: str) -> Optional[str]:
    """
    Fast keyword-based intent classification (no API call).

    Args:
        text: User input string.

    Returns:
        Intent string or None if ambiguous.
    """
    t = text.lower()
    if any(w in t for w in ["draft", "file rti", "write rti", "apply for rti", "want information"]):
        return "draft"
    if any(w in t for w in ["appeal", "first appeal", "second appeal", "denied"]):
        return "appeal"
    if any(w in t for w in ["classify", "parse response", "government reply", "analyse response"]):
        return "parse_response"
    if any(w in t for w in ["track", "status", "deadline", "days remaining", "overdue"]):
        return "track"
    if any(w in t for w in ["right", "section", "law", "act", "can i", "what is", "who is",
                              "how do", "explain", "penalty", "fee", "exempt", "pio", "cic"]):
        return "rights_question"
    return None


def _llm_intent(text: str) -> str:
    """
    LLM-based intent classification using Groq (with OpenAI fallback).

    Args:
        text: User input string.

    Returns:
        One of: draft, rights_question, parse_response, appeal, track.
    """
    prompt = INTENT_CLASSIFIER_PROMPT.format(user_input=text)
    valid_intents = {"draft", "rights_question", "parse_response", "appeal", "track"}
    try:
        client = Groq(api_key=settings.groq_api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        intent = resp.choices[0].message.content.strip().lower()
    except Exception:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=10,
            )
            intent = resp.choices[0].message.content.strip().lower()
        except Exception:
            intent = "rights_question"

    return intent if intent in valid_intents else "rights_question"


# ─── Graph Nodes ───────────────────────────────────────────────────────────────

def intent_classifier_node(state: RTIState) -> RTIState:
    """
    Classify the user's intent using keyword heuristics + LLM fallback.

    Args:
        state: Current graph state.

    Returns:
        Updated state with 'intent' field set.
    """
    user_input = state.get("user_input", "")
    intent = _keyword_intent(user_input) or _llm_intent(user_input)
    return {**state, "intent": intent}


def draft_node(state: RTIState) -> RTIState:
    """
    Execute the draft agent using context from the state.

    Args:
        state: Current graph state. Expects 'context' with draft fields.

    Returns:
        Updated state with 'draft_result' and 'final_response'.
    """
    ctx = state.get("context", {})
    try:
        result = run_draft_agent(
            citizen_request=ctx.get("citizen_request", state.get("user_input", "")),
            department_name=ctx.get("department_name", "Central Government"),
            citizen_name=ctx.get("citizen_name", "Citizen"),
            citizen_address=ctx.get("citizen_address", "India"),
            citizen_email=ctx.get("citizen_email", "citizen@example.com"),
            is_bpl=ctx.get("is_bpl", False),
        )
        return {**state, "draft_result": result, "final_response": result}
    except Exception as e:
        return {**state, "error": str(e), "final_response": {"error": str(e)}}


def rag_node(state: RTIState) -> RTIState:
    """
    Execute the RAG agent to answer a rights question.

    Args:
        state: Current graph state. Uses 'user_input' as the question.

    Returns:
        Updated state with 'rag_result' and 'final_response'.
    """
    question = state.get("user_input", "")
    try:
        result = run_rag_agent(question)
        return {**state, "rag_result": result, "final_response": result}
    except Exception as e:
        return {**state, "error": str(e), "final_response": {"error": str(e)}}


def response_node(state: RTIState) -> RTIState:
    """
    Execute the response classifier agent.

    Args:
        state: Current graph state. Expects 'context' with response_text or pdf_path.

    Returns:
        Updated state with 'response_result' and 'final_response'.
    """
    ctx = state.get("context", {})
    try:
        result = run_response_agent(
            pdf_path=ctx.get("pdf_path"),
            response_text=ctx.get("response_text", state.get("user_input", "")),
        )
        return {**state, "response_result": result, "final_response": result}
    except Exception as e:
        return {**state, "error": str(e), "final_response": {"error": str(e)}}


def appeal_node(state: RTIState) -> RTIState:
    """
    Execute the appeal drafting agent.

    Args:
        state: Current graph state. Expects 'context' with response_text and classification.

    Returns:
        Updated state with 'appeal_result' and 'final_response'.
    """
    ctx = state.get("context", {})
    try:
        result = run_appeal_agent(
            response_text=ctx.get("response_text", ""),
            classification=ctx.get("classification", "NO_RESPONSE"),
            appellant_name=ctx.get("appellant_name"),
            appellant_address=ctx.get("appellant_address"),
            department_name=ctx.get("department_name"),
            rti_subject=ctx.get("rti_subject"),
            date_filed=ctx.get("date_filed"),
        )
        return {**state, "appeal_result": result, "final_response": result}
    except Exception as e:
        return {**state, "error": str(e), "final_response": {"error": str(e)}}


def track_node(state: RTIState) -> RTIState:
    """
    Fetch deadline and status information for an RTI application.

    Args:
        state: Current graph state. Expects 'context' with application_id.

    Returns:
        Updated state with tracking info in 'final_response'.
    """
    ctx = state.get("context", {})
    application_id = ctx.get("application_id")
    db = SessionLocal()
    try:
        if not application_id:
            return {**state, "final_response": {"error": "No application_id provided."}}

        app = crud.get_application_by_id(db, application_id)
        if not app:
            return {**state, "final_response": {"error": f"Application {application_id} not found."}}

        dept = crud.get_department_by_id(db, app.department_id)
        timeline = get_status_timeline(application_id, db)
        result = {
            "application_number": app.application_number,
            "subject": app.subject,
            "department": dept.name if dept else "Unknown",
            "status": app.status,
            "date_filed": app.date_filed.strftime("%Y-%m-%d"),
            "deadline_date": app.deadline_date.strftime("%Y-%m-%d"),
            "days_remaining": get_days_remaining(app),
            "is_overdue": is_overdue(app),
            "timeline": timeline,
        }
        return {**state, "final_response": result}
    except Exception as e:
        return {**state, "error": str(e), "final_response": {"error": str(e)}}
    finally:
        db.close()


# ─── Routing Logic ─────────────────────────────────────────────────────────────

def route_by_intent(state: RTIState) -> str:
    """
    Determine which node to route to based on the classified intent.

    Args:
        state: Current graph state with 'intent' set.

    Returns:
        Node name string.
    """
    intent_map = {
        "draft": "draft_node",
        "rights_question": "rag_node",
        "parse_response": "response_node",
        "appeal": "appeal_node",
        "track": "track_node",
    }
    return intent_map.get(state.get("intent", ""), "rag_node")


# ─── Build Graph ───────────────────────────────────────────────────────────────

def build_orchestrator() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph for the RTI assistant.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    graph = StateGraph(RTIState)

    # Add nodes
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("draft_node", draft_node)
    graph.add_node("rag_node", rag_node)
    graph.add_node("response_node", response_node)
    graph.add_node("appeal_node", appeal_node)
    graph.add_node("track_node", track_node)

    # Entry point
    graph.set_entry_point("intent_classifier")

    # Conditional routing from intent_classifier
    graph.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "draft_node": "draft_node",
            "rag_node": "rag_node",
            "response_node": "response_node",
            "appeal_node": "appeal_node",
            "track_node": "track_node",
        },
    )

    # All agent nodes go to END
    for node in ["draft_node", "rag_node", "response_node", "appeal_node", "track_node"]:
        graph.add_edge(node, END)

    return graph.compile()


# Module-level compiled graph instance
_orchestrator = None


def get_orchestrator():
    """
    Return (and lazily build) the compiled orchestrator graph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = build_orchestrator()
    return _orchestrator


def run_orchestrator(user_input: str, context: Optional[Dict] = None) -> Dict:
    """
    Run the full orchestrator pipeline on a user input.

    Args:
        user_input: The user's message or question.
        context: Optional dict with additional parameters for agents.

    Returns:
        The 'final_response' dict from the executed agent node.
    """
    # Input validation guardrail
    is_valid, error_msg = _validate_input(user_input)
    if not is_valid:
        return {"error": error_msg}
    
    # Sanitize input
    user_input = _sanitize_input(user_input)
    
    orchestrator = get_orchestrator()
    initial_state: RTIState = {
        "user_input": user_input,
        "context": context or {},
    }
    
    try:
        final_state = orchestrator.invoke(initial_state)
        return final_state.get("final_response", {"error": "No response generated."})
    except Exception as e:
        return {"error": f"Orchestrator failed: {str(e)}"}

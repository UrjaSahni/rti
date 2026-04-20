"""
Evaluation: End-to-End Scenarios.

Runs 5 complete pipeline scenarios to verify all agents work together.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from app.database.models import SessionLocal, create_tables
from app.database import crud
from app.utils.deadline_tracker import is_overdue, get_days_remaining
from evaluation.eval_draft import evaluate_draft


def run_e2e_eval() -> Dict:
    """
    Run 5 end-to-end evaluation scenarios.

    Scenario 1: RTI Draft generation and quality check
    Scenario 2: Rights Q&A via RAG agent
    Scenario 3: Response classification (DENIED case)
    Scenario 4: Appeal draft generation
    Scenario 5: Deadline overdue detection

    Returns:
        Dict with status (PASS/FAIL), passed count, total=5, scenario details.
    """
    create_tables()

    scenarios = []
    passed = 0

    # ── Scenario 1: RTI Draft ───────────────────────────────────────────────
    print("[e2e] Scenario 1: RTI Draft generation...")
    try:
        from app.agents.draft_agent import run_draft_agent
        result = run_draft_agent(
            citizen_request="I want to know the status of my EPFO pension claim filed 6 months ago",
            department_name="EPFO",
            citizen_name="Test Citizen",
            citizen_address="123 Test Street, New Delhi",
            citizen_email="e2e_test_s1@eval.com",
            is_bpl=False,
        )
        eval_result = evaluate_draft(result.get("draft_text", ""))
        s1_pass = eval_result.get("passed", False)
        detail = {
            "scenario": "RTI Draft",
            "passed": s1_pass,
            "score": eval_result.get("completeness_score", 0.0),
            "missing": eval_result.get("missing", []),
        }
    except Exception as e:
        s1_pass = False
        detail = {"scenario": "RTI Draft", "passed": False, "error": str(e)}
    scenarios.append(detail)
    if s1_pass:
        passed += 1
    print(f"  {'PASS' if s1_pass else 'FAIL'}: {detail}")

    # ── Scenario 2: Rights Q&A ──────────────────────────────────────────────
    print("[e2e] Scenario 2: Rights Q&A...")
    try:
        from app.agents.rag_agent import run_rag_agent
        result = run_rag_agent("What happens if my RTI is not answered in 30 days?")
        answer = result.get("answer", "").lower()
        s2_pass = (
            "section 7" in answer
            and ("deemed" in answer or "refusal" in answer or "appeal" in answer)
        )
        detail = {
            "scenario": "Rights Q&A",
            "passed": s2_pass,
            "answer_preview": answer[:200],
        }
    except Exception as e:
        s2_pass = False
        detail = {"scenario": "Rights Q&A", "passed": False, "error": str(e)}
    scenarios.append(detail)
    if s2_pass:
        passed += 1
    print(f"  {'PASS' if s2_pass else 'FAIL'}: passed={s2_pass}")

    # ── Scenario 3: Response Classification ────────────────────────────────
    print("[e2e] Scenario 3: Response Classification...")
    try:
        from app.agents.response_agent import run_response_agent

        # Create a test application in DB for this scenario
        db = SessionLocal()
        citizen = crud.create_citizen(
            db, "E2E Test User S3", "e2e_test_s3@eval.com", "9999999999", "Test Address"
        )
        dept = crud.get_department_by_name(db, "EPFO")
        dept_id = dept.id if dept else 1
        app = crud.create_rti_application(
            db, citizen.id, dept_id,
            "Test S3 Subject", "Test info requested",
            "Test draft text",
        )
        app_id = app.id
        db.close()

        denied_text = (
            "The information sought is exempted under Section 8(1)(j) of the RTI Act "
            "as it pertains to personal information the disclosure of which has no relationship "
            "to any public activity or interest."
        )
        result = run_response_agent(
            application_id=app_id,
            response_text=denied_text,
        )
        s3_pass = (
            result.get("classification") == "DENIED"
            and result.get("confidence", 0) >= 0.7
        )
        detail = {
            "scenario": "Response Classification",
            "passed": s3_pass,
            "classification": result.get("classification"),
            "confidence": result.get("confidence"),
        }
    except Exception as e:
        s3_pass = False
        detail = {"scenario": "Response Classification", "passed": False, "error": str(e)}
    scenarios.append(detail)
    if s3_pass:
        passed += 1
    print(f"  {'PASS' if s3_pass else 'FAIL'}: {detail}")

    # ── Scenario 4: Appeal Draft ────────────────────────────────────────────
    print("[e2e] Scenario 4: Appeal Draft...")
    try:
        from app.agents.appeal_agent import run_appeal_agent

        # Create test application + DENIED response
        db = SessionLocal()
        citizen = crud.create_citizen(
            db, "E2E Test User S4", "e2e_test_s4@eval.com", "8888888888", "Test Address"
        )
        dept = crud.get_department_by_name(db, "Delhi Police")
        dept_id = dept.id if dept else 1
        app = crud.create_rti_application(
            db, citizen.id, dept_id,
            "Test S4 Subject", "Test info requested",
            "Test draft text",
        )
        crud.create_government_response(
            db=db,
            application_id=app.id,
            response_type="DENIED",
            response_text="Information denied under Section 8(1)(j).",
            confidence=0.9,
            summary="DENIED: Section 8 exemption cited.",
        )
        app_id = app.id
        db.close()

        result = run_appeal_agent(application_id=app_id)
        appeal_text = result.get("appeal_text", "").lower()
        s4_pass = (
            "section 19" in appeal_text
            and "first appellate authority" in appeal_text
        )
        detail = {
            "scenario": "Appeal Draft",
            "passed": s4_pass,
            "appeal_preview": appeal_text[:200],
        }
    except Exception as e:
        s4_pass = False
        detail = {"scenario": "Appeal Draft", "passed": False, "error": str(e)}
    scenarios.append(detail)
    if s4_pass:
        passed += 1
    print(f"  {'PASS' if s4_pass else 'FAIL'}: passed={s4_pass}")

    # ── Scenario 5: Deadline Tracking (overdue) ────────────────────────────
    print("[e2e] Scenario 5: Overdue Detection...")
    try:
        db = SessionLocal()
        citizen = crud.create_citizen(
            db, "E2E Test User S5", "e2e_test_s5@eval.com", "7777777777", "Test Address"
        )
        dept = crud.get_department_by_name(db, "CBSE")
        dept_id = dept.id if dept else 1
        # Create application filed 35 days ago → overdue
        old_app = crud.create_rti_application(
            db, citizen.id, dept_id,
            "Overdue Test Subject", "Test info requested",
            "Test draft text",
        )
        # Manually set date to 35 days ago
        from datetime import timedelta
        old_date = date.today() - timedelta(days=35)
        old_app.date_filed = old_date
        old_app.deadline_date = old_date + timedelta(days=30)
        old_app.status = "SUBMITTED"
        db.commit()
        db.refresh(old_app)

        overdue_result = is_overdue(old_app)
        days_result = get_days_remaining(old_app)
        db.close()

        s5_pass = overdue_result is True and days_result < 0
        detail = {
            "scenario": "Overdue Detection",
            "passed": s5_pass,
            "is_overdue": overdue_result,
            "days_remaining": days_result,
        }
    except Exception as e:
        s5_pass = False
        detail = {"scenario": "Overdue Detection", "passed": False, "error": str(e)}
    scenarios.append(detail)
    if s5_pass:
        passed += 1
    print(f"  {'PASS' if s5_pass else 'FAIL'}: {detail}")

    # ── Summary ─────────────────────────────────────────────────────────────
    status = "PASS" if passed >= 4 else "FAIL"
    print(f"\n[e2e] E2E Test Results: {passed}/5 scenarios passed → {status}")

    output = {
        "status": status,
        "passed": passed,
        "total": 5,
        "scenarios": scenarios,
    }

    out_path = RESULTS_DIR / "e2e_eval.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[e2e] Results saved: {out_path}")
    return output


if __name__ == "__main__":
    run_e2e_eval()

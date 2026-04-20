"""
Evaluation: Deadline Tracker and Fee Waiver.

Runs 10 deterministic unit tests against the deadline_tracker module.
No LLM calls required — purely date arithmetic and logic.
"""
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

from app.utils.deadline_tracker import calculate_deadline, check_fee_waiver


# ─── Mock application object for is_overdue / get_days_remaining tests ─────────

class MockApplication:
    """Minimal mock RTI application for deadline testing."""
    def __init__(self, deadline_date: date, status: str = "SUBMITTED"):
        self.deadline_date = deadline_date
        self.status = status


def run_deadline_eval() -> Dict:
    """
    Run all 10 deadline and fee waiver unit tests.

    Tests:
    1.  Normal deadline: filed 2025-01-01 → deadline 2025-01-31
    2.  Life/liberty deadline: filed 2025-01-01 → deadline 2025-01-03
    3.  First appeal deadline: filed 2025-03-01 → deadline 2025-03-31
    4.  Second appeal deadline: filed 2025-03-01 → deadline 2025-05-30
    5.  Transfer deadline: filed 2025-01-01 → deadline 2025-01-06
    6.  is_overdue True: past deadline, SUBMITTED status
    7.  is_overdue False: future deadline
    8.  days_remaining positive: future deadline
    9.  days_remaining negative: past deadline
    10. BPL fee waiver: is_bpl=True → fee=0, waiver_applied=True

    Returns:
        Dict with status (PASS/FAIL), passed_tests count, total_tests.
    """
    from app.utils.deadline_tracker import is_overdue, get_days_remaining

    tests = []

    # ── Test 1: Normal deadline ─────────────────────────────────────────────
    result = calculate_deadline(date(2025, 1, 1), "normal")
    expected = date(2025, 1, 31)
    passed = result == expected
    tests.append({
        "name": "test_normal_deadline",
        "passed": passed,
        "expected": str(expected),
        "actual": str(result),
    })

    # ── Test 2: Life/liberty deadline ──────────────────────────────────────
    result = calculate_deadline(date(2025, 1, 1), "life_liberty")
    expected = date(2025, 1, 3)
    passed = result == expected
    tests.append({
        "name": "test_life_liberty",
        "passed": passed,
        "expected": str(expected),
        "actual": str(result),
    })

    # ── Test 3: First appeal deadline ──────────────────────────────────────
    result = calculate_deadline(date(2025, 3, 1), "first_appeal")
    expected = date(2025, 3, 31)
    passed = result == expected
    tests.append({
        "name": "test_first_appeal",
        "passed": passed,
        "expected": str(expected),
        "actual": str(result),
    })

    # ── Test 4: Second appeal deadline ─────────────────────────────────────
    result = calculate_deadline(date(2025, 3, 1), "second_appeal")
    expected = date(2025, 5, 30)
    passed = result == expected
    tests.append({
        "name": "test_second_appeal",
        "passed": passed,
        "expected": str(expected),
        "actual": str(result),
    })

    # ── Test 5: Transfer deadline ───────────────────────────────────────────
    result = calculate_deadline(date(2025, 1, 1), "transfer")
    expected = date(2025, 1, 6)
    passed = result == expected
    tests.append({
        "name": "test_transfer",
        "passed": passed,
        "expected": str(expected),
        "actual": str(result),
    })

    # ── Test 6: is_overdue True ─────────────────────────────────────────────
    past_app = MockApplication(deadline_date=date(2020, 1, 1), status="SUBMITTED")
    result = is_overdue(past_app)
    passed = result is True
    tests.append({
        "name": "test_overdue_true",
        "passed": passed,
        "expected": True,
        "actual": result,
    })

    # ── Test 7: is_overdue False ────────────────────────────────────────────
    future_app = MockApplication(deadline_date=date(2099, 12, 31), status="SUBMITTED")
    result = is_overdue(future_app)
    passed = result is False
    tests.append({
        "name": "test_overdue_false",
        "passed": passed,
        "expected": False,
        "actual": result,
    })

    # ── Test 8: days_remaining positive ────────────────────────────────────
    future_app2 = MockApplication(deadline_date=date(2099, 12, 31), status="SUBMITTED")
    result = get_days_remaining(future_app2)
    passed = result > 0
    tests.append({
        "name": "test_days_remaining_positive",
        "passed": passed,
        "expected": "> 0",
        "actual": result,
    })

    # ── Test 9: days_remaining negative ────────────────────────────────────
    past_app2 = MockApplication(deadline_date=date(2020, 1, 1), status="SUBMITTED")
    result = get_days_remaining(past_app2)
    passed = result < 0
    tests.append({
        "name": "test_days_remaining_negative",
        "passed": passed,
        "expected": "< 0",
        "actual": result,
    })

    # ── Test 10: BPL fee waiver ─────────────────────────────────────────────
    result = check_fee_waiver(is_bpl=True)
    passed = result["fee_amount"] == 0.0 and result["waiver_applied"] is True
    tests.append({
        "name": "test_bpl_fee_waiver",
        "passed": passed,
        "expected": {"fee_amount": 0.0, "waiver_applied": True},
        "actual": {"fee_amount": result["fee_amount"], "waiver_applied": result["waiver_applied"]},
    })

    # ── Summary ─────────────────────────────────────────────────────────────
    passed_count = sum(1 for t in tests if t["passed"])
    total = len(tests)
    status = "PASS" if passed_count == total else "FAIL"

    for t in tests:
        icon = "✓" if t["passed"] else "✗"
        print(f"  [{icon}] {t['name']}: expected={t['expected']}, actual={t['actual']}")

    print(f"\n[eval_deadline] {passed_count}/{total} tests passed → {status}")

    output = {
        "status": status,
        "passed_tests": passed_count,
        "total_tests": total,
        "tests": tests,
    }

    out_path = RESULTS_DIR / "deadline_eval.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[eval_deadline] Results saved: {out_path}")
    return output


if __name__ == "__main__":
    run_deadline_eval()

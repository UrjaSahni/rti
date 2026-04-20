"""
Master evaluation runner — runs all 6 evaluation components and
produces a final scorecard report.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.eval_draft import run_draft_eval
from evaluation.eval_rag import run_rag_eval
from evaluation.eval_classifier import run_classifier_eval
from evaluation.eval_deadline import run_deadline_eval
from evaluation.eval_e2e import run_e2e_eval
from evaluation.eval_ethics import run_ethics_eval

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    """
    Run the complete RTI Assistant Evaluation Suite.

    Executes all 6 evaluations in sequence, prints a formatted scorecard,
    and saves the consolidated report to evaluation/results/final_report.json.
    """
    print("Running RTI Assistant Evaluation Suite...")
    print("=" * 60)

    results = {}

    print("\n[1/6] DRAFT QUALITY EVALUATION")
    print("-" * 40)
    results["draft"] = run_draft_eval()

    print("\n[2/6] RAG Q&A ACCURACY EVALUATION")
    print("-" * 40)
    results["rag"] = run_rag_eval()

    print("\n[3/6] CLASSIFIER EVALUATION")
    print("-" * 40)
    results["classifier"] = run_classifier_eval()

    print("\n[4/6] DEADLINE TRACKER EVALUATION")
    print("-" * 40)
    results["deadline"] = run_deadline_eval()

    print("\n[5/6] END-TO-END EVALUATION")
    print("-" * 40)
    results["e2e"] = run_e2e_eval()

    print("\n[6/6] ETHICS EVALUATION")
    print("-" * 40)
    results["ethics"] = run_ethics_eval()

    # ── Final Scorecard ─────────────────────────────────────────────────────
    passed = sum(1 for r in results.values() if r.get("status") == "PASS")
    total = len(results)

    print("\n" + "=" * 60)
    print("FINAL EVALUATION SCORECARD")
    print("=" * 60)

    score_keys = {
        "draft": "score",
        "rag": "accuracy",
        "classifier": "accuracy",
        "deadline": "passed_tests",
        "e2e": "passed",
        "ethics": "disclaimer_rate",
    }

    for component, result in results.items():
        status = result.get("status", "UNKNOWN")
        score_key = score_keys.get(component, "score")
        score_val = result.get(score_key, "N/A")
        icon = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{icon}] {component.upper():20} {score_key}: {score_val}")

    print(f"\n  OVERALL: {passed}/{total} components passed")
    if passed >= 5:
        overall_status = "READY FOR PRESENTATION"
    elif passed >= 3:
        overall_status = "MOSTLY READY — fix failing components"
    else:
        overall_status = "NEEDS WORK — multiple components failing"
    print(f"  STATUS: {overall_status}")
    print("=" * 60)

    # Save consolidated report
    final_report = {
        "components": results,
        "summary": {
            "passed": passed,
            "total": total,
            "status": "READY" if passed >= 5 else "NEEDS WORK",
        },
    }
    out_path = RESULTS_DIR / "final_report.json"
    with open(out_path, "w") as f:
        json.dump(final_report, f, indent=2, default=str)

    print(f"\nFull report saved: {out_path}")


if __name__ == "__main__":
    main()

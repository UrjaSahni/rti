"""
Evaluation: RAG Q&A Accuracy.

Tests the RAG agent on 20 golden Q&A pairs.
Checks: keyword coverage, correct section citations, no hallucinations.
"""
import re
import json
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
GOLDEN_PATH = PROJECT_ROOT / "evaluation" / "golden_qa_pairs.json"


def _check_no_hallucination(answer: str, max_section: int = 31) -> bool:
    """
    Return True if no section number above max_section is cited.

    Args:
        answer: LLM-generated answer text.
        max_section: Maximum valid RTI section number (31).

    Returns:
        True if no hallucinated sections; False if any > max_section found.
    """
    nums = [int(m) for m in re.findall(r"[Ss]ection\s+(\d+)", answer)]
    return all(n <= max_section for n in nums)


def _score_question(answer: str, qa_pair: Dict) -> Dict:
    """
    Score a single Q&A pair.

    Scoring:
    - keywords_score  : fraction of expected keywords found in answer
    - section_correct : 1.0 if expected section is cited, else 0.0
    - no_hallucination: 1.0 if no section > 31 cited
    - overall         : mean of the three

    Args:
        answer: RAG agent answer text.
        qa_pair: Golden Q&A dict with expected_answer_contains and expected_section.

    Returns:
        Dict with individual scores and overall score.
    """
    answer_lower = answer.lower()

    # Keyword check
    keywords = qa_pair.get("expected_answer_contains", [])
    found = sum(1 for kw in keywords if kw.lower() in answer_lower)
    keywords_score = found / len(keywords) if keywords else 1.0

    # Section check
    expected_section = str(qa_pair.get("expected_section", ""))
    section_found = bool(re.search(rf"[Ss]ection\s+{expected_section}\b", answer))
    section_score = 1.0 if section_found else 0.0

    # Hallucination check
    no_hallucination = 1.0 if _check_no_hallucination(answer) else 0.0

    overall = (keywords_score + section_score + no_hallucination) / 3.0

    return {
        "question": qa_pair["question"],
        "category": qa_pair.get("category", "unknown"),
        "keywords_found": found,
        "keywords_total": len(keywords),
        "keywords_score": round(keywords_score, 2),
        "expected_section": expected_section,
        "section_correct": section_found,
        "no_hallucination": no_hallucination == 1.0,
        "overall_score": round(overall, 2),
        "fully_correct": (keywords_score >= 0.6 and section_found and no_hallucination == 1.0),
        "answer_preview": answer[:300],
    }


def run_rag_eval() -> Dict:
    """
    Run RAG evaluation on all 20 golden Q&A pairs.

    For each question:
    1. Calls run_rag_agent(question)
    2. Evaluates keyword coverage, section accuracy, hallucination

    Returns:
        Dict with status (PASS/FAIL), accuracy, and per_question details.
    """
    from app.agents.rag_agent import run_rag_agent

    with open(GOLDEN_PATH, "r") as f:
        qa_pairs = json.load(f)

    print(f"[eval_rag] Running {len(qa_pairs)} Q&A evaluations...")
    per_question = []
    total_score = 0.0
    fully_correct = 0

    for i, qa in enumerate(qa_pairs):
        print(f"  [{i + 1}/{len(qa_pairs)}] {qa['question'][:60]}...")
        try:
            result = run_rag_agent(qa["question"])
            answer = result.get("answer", "")
        except Exception as e:
            print(f"    [warn] RAG agent failed: {e}")
            answer = ""

        scores = _score_question(answer, qa)
        per_question.append(scores)
        total_score += scores["overall_score"]
        if scores["fully_correct"]:
            fully_correct += 1

    accuracy = round(total_score / len(qa_pairs), 3) if qa_pairs else 0.0
    status = "PASS" if accuracy >= 0.7 else "FAIL"

    print(f"\n[eval_rag] RAG Accuracy: {fully_correct}/{len(qa_pairs)} questions fully correct")
    print(f"[eval_rag] Average Score: {accuracy:.3f} → {status}")

    output = {
        "status": status,
        "accuracy": accuracy,
        "fully_correct": fully_correct,
        "total": len(qa_pairs),
        "per_question": per_question,
    }

    out_path = RESULTS_DIR / "rag_eval.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[eval_rag] Results saved: {out_path}")
    return output


if __name__ == "__main__":
    run_rag_eval()

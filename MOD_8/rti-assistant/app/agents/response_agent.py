"""
Response Agent — parses and classifies government RTI responses.

Accepts either a PDF path or plain response text.
Uses Groq primary / OpenAI fallback for classification.

REFACTORED: No database dependency. Returns raw_text for appeal generation.
"""
import re
from pathlib import Path
from typing import Dict, Optional

from groq import Groq
from openai import OpenAI

from app.config import settings
from app.utils.prompt_templates import RESPONSE_CLASSIFIER_PROMPT
from app.utils.pdf_parser import parse_pdf


# Recommended actions per classification
RECOMMENDED_ACTIONS = {
    "ALLOWED": "Your RTI was successful. Request the information in writing.",
    "PARTIAL": "File appeal for complete information within 30 days under Section 19(1).",
    "DENIED": "File a first appeal within 30 days under Section 19(1) of the RTI Act.",
    "TRANSFERRED": "Follow up with the new department within 15 days.",
    "NO_RESPONSE": "File first appeal immediately — deemed refusal under Section 7(2).",
}

# Next step recommendations per classification (user-facing, concise)
NEXT_STEP_ACTIONS = {
    "ALLOWED": "No further action required.",
    "DENIED": "File first appeal under Section 19(1) within 30 days.",
    "PARTIAL": "File appeal if information is incomplete.",
    "TRANSFERRED": "Wait for response from transferred department.",
    "NO_RESPONSE": "File first appeal under Section 7(2).",
}


def _call_groq(prompt: str) -> str:
    """
    Call Groq API for classification.

    Args:
        prompt: Fully-formatted classification prompt.

    Returns:
        LLM response text.
    """
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    """
    Call OpenAI API as fallback for classification.

    Args:
        prompt: Fully-formatted classification prompt.

    Returns:
        LLM response text.
    """
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    return response.choices[0].message.content.strip()


def _call_llm(prompt: str) -> str:
    """
    Call Groq; fall back to OpenAI on any exception.

    Args:
        prompt: Fully-formatted prompt string.

    Returns:
        LLM response text.

    Raises:
        RuntimeError: If both providers fail.
    """
    try:
        return _call_groq(prompt)
    except Exception as groq_err:
        print(f"[response_agent] Groq failed ({groq_err}). Falling back to OpenAI...")
        try:
            return _call_openai(prompt)
        except Exception as oai_err:
            raise RuntimeError(
                f"Both LLMs failed. Groq: {groq_err} | OpenAI: {oai_err}"
            )


def _parse_llm_classification(raw: str) -> Dict:
    """
    Parse the LLM classification output into structured fields.

    Expected format:
        Category: DENIED
        Confidence: 0.95
        Reason: The response cites Section 8 exemption.

    Args:
        raw: Raw LLM output string.

    Returns:
        Dict with keys: category, confidence, reason.
    """
    category = "NO_RESPONSE"
    confidence = 0.5
    reason = ""

    cat_match = re.search(
        r"Category:\s*(ALLOWED|PARTIAL|DENIED|TRANSFERRED|NO_RESPONSE)",
        raw, re.IGNORECASE
    )
    if cat_match:
        category = cat_match.group(1).upper()

    conf_match = re.search(r"Confidence:\s*([\d.]+)", raw)
    if conf_match:
        try:
            raw_conf = float(conf_match.group(1))
            # Normalise: LLMs sometimes return 95 instead of 0.95
            if raw_conf > 1.0:
                raw_conf = raw_conf / 100.0
            # Clamp to realistic range — never allow 100% certainty from LLM
            confidence = max(0.50, min(0.98, raw_conf))
        except ValueError:
            confidence = 0.75
    else:
        # No confidence field in LLM output — assign a sensible default per category
        defaults = {
            "DENIED": 0.92, "TRANSFERRED": 0.90,
            "PARTIAL": 0.87, "NO_RESPONSE": 0.85, "ALLOWED": 0.88,
        }
        confidence = defaults.get(category, 0.75)

    reason_match = re.search(r"Reason:\s*(.+)", raw, re.IGNORECASE)
    if reason_match:
        reason = reason_match.group(1).strip()

    return {"category": category, "confidence": confidence, "reason": reason}


def _keyword_fallback_classify(text: str) -> Dict:
    """
    Priority-ordered keyword classifier used when the LLM is unavailable.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  CRITICAL: ALLOWED must have HIGHEST PRIORITY                            ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║  Rationale: Government responses that explicitly provide information     ║
    ║  (e.g., "information is enclosed", "documents attached") should ALWAYS   ║
    ║  be classified as ALLOWED, even if the text contains ambiguous phrases   ║
    ║  that might match other categories.                                      ║
    ║                                                                          ║
    ║  Example: "The requested information is enclosed herewith. Copies of     ║
    ║  all documents are attached." — This MUST be ALLOWED, not NO_RESPONSE.   ║
    ║                                                                          ║
    ║  Without ALLOWED as highest priority, responses providing information    ║
    ║  could be misclassified as NO_RESPONSE (the default fallback), causing   ║
    ║  citizens to unnecessarily file appeals for already-granted requests.    ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    Priority (highest → lowest):
      1. ALLOWED     — information fully provided (MUST check first!)
      2. DENIED      — explicit Section 8 exemption cited
      3. PARTIAL     — some info given, rest withheld
      4. TRANSFERRED — Section 6(3) transfer
      5. NO_RESPONSE — delay / deemed refusal (default fallback)

    Args:
        text: Government response text (plain string).

    Returns:
        Dict with keys: category (str), confidence (float), reason (str).
    """
    # Preprocess: lowercase and remove extra whitespace
    t = " ".join(text.lower().split())

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 1 (HIGHEST): ALLOWED — Information fully provided
    # ══════════════════════════════════════════════════════════════════════════
    # MUST be checked FIRST! Responses that clearly provide information should
    # immediately return ALLOWED to prevent misclassification as NO_RESPONSE.
    # These phrases indicate the RTI request was successful and info is enclosed.
    allowed_patterns = [
        r"information\s+is\s+enclosed",           # "information is enclosed"
        r"documents?\s+attached",                 # "documents attached"
        r"copies\s+of\s+documents",               # "copies of documents"
        r"information\s+is\s+hereby\s+provided",  # "information is hereby provided"
        r"enclosed\s+herewith",                   # "enclosed herewith"
        r"no\s+further\s+action\s+(?:is\s+)?required",  # "no further action is required"
        r"information\s+(?:is\s+)?(?:attached|provided|furnished)",
        r"please\s+find\s+(?:enclosed|attached|herewith)",
        r"hereby\s+(?:provided|furnished|supplied)",
        r"\bprovided\s+(?:as\s+requested|herewith|below)\b",
        r"details?\s+(?:are\s+)?(?:given|enclosed|provided)\s+(?:below|herewith)",
        r"requested\s+(?:information|documents?)\s+(?:is|are)\s+(?:enclosed|attached|provided)",
    ]
    if any(re.search(p, t) for p in allowed_patterns):
        return {"category": "ALLOWED", "confidence": 0.95,
                "reason": "Response explicitly provides/encloses the requested information."}

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 2: DENIED — Explicit Section 8 exemption cited
    # ══════════════════════════════════════════════════════════════════════════
    # Must cite Section 8 or explicit refusal on merits — NOT a timing failure.
    denied_patterns = [
        r"section\s*8",                     # Section 8(1)(a)–(j) exemptions
        r"exempt\w*\s+(?:from\s+)?disclosure",  # "exempt from disclosure"
        r"cannot\s+be\s+(?:provided|disclosed)",  # "cannot be provided"
        r"exempt\w*\s+under",               # "exempted under ..."
        r"under\s+(?:an?\s+)?exemption",    # "withheld under exemption"
        r"withheld\s+\w+\s+exemption",      # "withheld under/citing exemption"
        r"not\s+maintainable",
        r"information\s+is\s+exempt",
        r"falls\s+under\s+exemption",
    ]
    if any(re.search(p, t) for p in denied_patterns):
        return {"category": "DENIED", "confidence": 0.95,
                "reason": "Response cites Section 8 exemption or explicit refusal on merits."}

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 3: PARTIAL — Some info given, rest withheld
    # ══════════════════════════════════════════════════════════════════════════
    partial_patterns = [
        r"partial\s+information",
        r"remaining\s+information\s+not\s+available",  # "remaining information not available"
        r"not\s+maintained",                           # "not maintained"
        r"some\s+(of\s+the\s+)?(?:information|records|documents)",
        r"remaining\s+(?:information|records|documents)\s+(?:not|are\s+not)\s+available",
        r"part\s+of\s+the\s+information",
        r"partially\s+(?:provided|disclosed|furnished)",
        r"certain\s+(?:information|records)\s+(?:are\s+)?withheld",
    ]
    if any(re.search(p, t) for p in partial_patterns):
        return {"category": "PARTIAL", "confidence": 0.90,
                "reason": "Response provides partial information, rest withheld."}

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 4: TRANSFERRED — Application forwarded under Section 6(3)
    # ══════════════════════════════════════════════════════════════════════════
    transferred_patterns = [
        r"transferred\s+under\s+section\s*6\s*\(\s*3\s*\)",  # "transferred under section 6(3)"
        r"does\s+not\s+pertain\s+to\s+this\s+department",   # "does not pertain to this department"
        r"section\s*6\s*\(\s*3\s*\)",
        r"transfer\w*\s+(?:the\s+)?application",
        r"forwarded\s+to",
        r"transferred\s+to",
    ]
    if any(re.search(p, t) for p in transferred_patterns):
        return {"category": "TRANSFERRED", "confidence": 0.92,
                "reason": "Response indicates transfer under Section 6(3)."}

    # ══════════════════════════════════════════════════════════════════════════
    # Priority 5 (LOWEST): NO_RESPONSE — Delay or deemed refusal
    # ══════════════════════════════════════════════════════════════════════════
    # This is NOT the same as DENIED. Deemed refusal means PIO did not respond.
    no_response_patterns = [
        r"\bdelay\b",                       # "delay"
        r"administrative\s+reasons",        # "administrative reasons"
        r"deemed\s+refusal",                # "deemed refusal"
        r"no\s+response",                   # "no response"
        r"not\s+(?:responded|replied)\s+within",
        r"delay\s+in\s+(?:providing|furnishing|responding)",
        r"information\s+not\s+provided\s+within\s+(?:time|\d+\s+days)",
        r"failed\s+to\s+(?:respond|reply|provide)",
        r"time\s+limit\s+(?:has\s+)?expired",
        r"30[\s-]day\s+period\s+(?:has\s+)?elapsed",
    ]
    if any(re.search(p, t) for p in no_response_patterns):
        return {"category": "NO_RESPONSE", "confidence": 0.90,
                "reason": "Delay or deemed refusal — no timely response from PIO."}

    # ══════════════════════════════════════════════════════════════════════════
    # Default fallback — check intelligibility before assuming NO_RESPONSE
    # ══════════════════════════════════════════════════════════════════════════
    # If the text is very short or consists mostly of non-alphabetic characters
    # (i.e. gibberish), return UNKNOWN instead of silently defaulting to
    # NO_RESPONSE, which would produce a misleading appeal letter.
    import re as _re
    alpha_chars = len(_re.sub(r'[^a-zA-Z]', '', t))
    total_chars = len(t)
    alpha_ratio = alpha_chars / total_chars if total_chars else 0
    word_count  = len(t.split())

    if word_count < 5 or alpha_ratio < 0.5:
        return {"category": "UNKNOWN", "confidence": 0.0,
                "reason": "Input appears to be gibberish or too short to classify."}

    return {"category": "NO_RESPONSE", "confidence": 0.55,
            "reason": "No clear classification signal found; defaulting to NO_RESPONSE."}


def run_response_agent(
    pdf_path: Optional[str] = None,
    response_text: Optional[str] = None,
) -> Dict:
    """
    Parse and classify a government RTI response.
    
    REFACTORED: No database dependency. Returns raw_text for appeal generation.

    Args:
        pdf_path: Path to a PDF file (optional).
        response_text: Plain text response (optional).
                       At least one of pdf_path or response_text must be provided.

    Returns:
        Dict with keys: classification, confidence, summary, recommended_action, raw_text.

    Raises:
        ValueError: If neither pdf_path nor response_text is provided.
    """
    if not pdf_path and not response_text:
        raise ValueError("Provide either pdf_path or response_text.")

    # Step 1: Extract text from PDF if provided
    if pdf_path:
        try:
            extracted = parse_pdf(pdf_path)
            response_text = extracted if extracted else (response_text or "")
        except Exception as e:
            print(f"[response_agent] PDF parsing failed: {e}. Using raw text.")
            response_text = response_text or ""

    if not response_text:
        response_text = "No response text available."

    # Step 2: Keyword-first classification
    # Run the rule-based classifier first. If it returns high confidence
    # (>= 0.87) it means a clear signal was found — trust it directly and
    # skip the LLM call entirely. This prevents the LLM from misclassifying
    # well-defined cases such as deemed refusal (NO_RESPONSE) as DENIED.
    keyword_result = _keyword_fallback_classify(response_text)

    # Short-circuit: gibberish / too-short input detected by keyword classifier.
    # Do NOT send to the LLM — it would silently default to NO_RESPONSE and
    # produce a misleading appeal letter.
    if keyword_result["category"] == "UNKNOWN":
        print("[response_agent] Input appears to be gibberish or too short. "
              "Returning UNKNOWN — skipping LLM call.")
        return {
            "classification": "UNKNOWN",
            "confidence": 0.0,
            "summary": "The text provided does not appear to be a valid government RTI response.",
            "recommended_action": (
                "Please paste the actual text of the government's RTI response. "
                "Gibberish or very short inputs cannot be classified."
            ),
            "raw_text": response_text,
        }

    if keyword_result["confidence"] >= 0.87:
        # High-confidence keyword match — no need to call the LLM
        print(f"[response_agent] Keyword classifier confident "
              f"({keyword_result['confidence']:.0%}) -> {keyword_result['category']}. "
              "Skipping LLM call.")
        parsed = keyword_result
    else:
        # Ambiguous text — let the LLM decide
        prompt = RESPONSE_CLASSIFIER_PROMPT.format(response_text=response_text[:4000])
        try:
            raw_output = _call_llm(prompt)
            parsed = _parse_llm_classification(raw_output)
        except Exception as e:
            print(f"[response_agent] LLM classification failed: {e}. Using keyword fallback.")
            parsed = keyword_result

    category = parsed["category"]
    confidence = parsed["confidence"]
    reason = parsed["reason"]
    summary = f"{category}: {reason}" if reason else category

    recommended_action = RECOMMENDED_ACTIONS.get(
        category,
        "Please review the response and consult the RTI Act for guidance."
    )

    return {
        "classification": category,
        "confidence": round(confidence, 3),
        "summary": summary,
        "recommended_action": recommended_action,
        "raw_text": response_text,  # Return for appeal generation
    }


def classify_rti_response(text: str) -> dict:
    """
    Standalone function to classify RTI response text using priority-ordered rules.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  WHY ALLOWED MUST HAVE HIGHEST PRIORITY                                  ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║  1. Positive outcomes should be recognized immediately — if a response   ║
    ║     says "information is enclosed", the citizen's request was fulfilled. ║
    ║                                                                          ║
    ║  2. Prevents false negatives — without this priority, responses like     ║
    ║     "The requested information is enclosed herewith" could be            ║
    ║     misclassified as NO_RESPONSE (the default fallback).                 ║
    ║                                                                          ║
    ║  3. Avoids unnecessary appeals — misclassifying ALLOWED as NO_RESPONSE   ║
    ║     would incorrectly advise citizens to file appeals for requests that  ║
    ║     were already granted.                                                ║
    ║                                                                          ║
    ║  4. Clear language deserves immediate recognition — phrases like         ║
    ║     "documents attached" or "copies of documents" are unambiguous        ║
    ║     indicators of successful RTI fulfillment.                            ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    Priority Order (VERY IMPORTANT):
        1. ALLOWED     — Information provided (HIGHEST PRIORITY - check first!)
        2. DENIED      — Section 8 exemption or explicit refusal
        3. PARTIAL     — Some info given, rest withheld
        4. TRANSFERRED — Forwarded to another department
        5. NO_RESPONSE — Delay or deemed refusal (lowest priority)

    Args:
        text: Government RTI response text (plain string).

    Returns:
        dict: {
            "classification": str,      # ALLOWED|DENIED|PARTIAL|TRANSFERRED|NO_RESPONSE
            "confidence": float,        # 0-100 scale
            "summary": str,             # Short explanation
            "next_step": str            # Recommended action
        }

    Example:
        >>> result = classify_rti_response(
        ...     "The requested information is enclosed herewith. "
        ...     "Copies of all documents are attached."
        ... )
        >>> result["classification"]
        'ALLOWED'
    """
    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Preprocess — lowercase and remove extra whitespace
    # ──────────────────────────────────────────────────────────────────────────
    t = " ".join(text.lower().split())

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Define keyword rules with PRIORITY ORDER
    # ──────────────────────────────────────────────────────────────────────────

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE 1 (HIGHEST PRIORITY): ALLOWED
    # ═══════════════════════════════════════════════════════════════════════════
    # MUST be checked FIRST! These phrases indicate information was provided.
    # If ANY of these match, return ALLOWED immediately — do NOT continue.
    allowed_keywords = [
        r"information\s+is\s+enclosed",           # "information is enclosed"
        r"documents?\s+attached",                 # "documents attached"
        r"copies\s+of\s+documents",               # "copies of documents"
        r"information\s+is\s+hereby\s+provided",  # "information is hereby provided"
        r"enclosed\s+herewith",                   # "enclosed herewith"
        r"no\s+further\s+action\s+(?:is\s+)?required",  # "no further action is required"
    ]
    if any(re.search(p, t) for p in allowed_keywords):
        return {
            "classification": "ALLOWED",
            "confidence": 95.0,
            "summary": "Response explicitly provides/encloses the requested information.",
            "next_step": NEXT_STEP_ACTIONS["ALLOWED"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE 2: DENIED — Section 8 exemption or explicit refusal
    # ═══════════════════════════════════════════════════════════════════════════
    denied_keywords = [
        r"section\s*8",                           # "section 8"
        r"exempt\s+from\s+disclosure",            # "exempt from disclosure"
        r"cannot\s+be\s+provided",                # "cannot be provided"
    ]
    if any(re.search(p, t) for p in denied_keywords):
        return {
            "classification": "DENIED",
            "confidence": 95.0,
            "summary": "Response cites Section 8 exemption or explicit refusal.",
            "next_step": NEXT_STEP_ACTIONS["DENIED"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE 3: PARTIAL — Some information given, rest withheld
    # ═══════════════════════════════════════════════════════════════════════════
    partial_keywords = [
        r"partial\s+information",                 # "partial information"
        r"remaining\s+information\s+not\s+available",  # "remaining information not available"
        r"not\s+maintained",                      # "not maintained"
    ]
    if any(re.search(p, t) for p in partial_keywords):
        return {
            "classification": "PARTIAL",
            "confidence": 90.0,
            "summary": "Response provides partial information; rest withheld or unavailable.",
            "next_step": NEXT_STEP_ACTIONS["PARTIAL"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE 4: TRANSFERRED — Application forwarded to another department
    # ═══════════════════════════════════════════════════════════════════════════
    transferred_keywords = [
        r"transferred\s+under\s+section\s*6\s*\(\s*3\s*\)",  # "transferred under section 6(3)"
        r"does\s+not\s+pertain\s+to\s+this\s+department",   # "does not pertain to this department"
    ]
    if any(re.search(p, t) for p in transferred_keywords):
        return {
            "classification": "TRANSFERRED",
            "confidence": 92.0,
            "summary": "Response indicates transfer to another department under Section 6(3).",
            "next_step": NEXT_STEP_ACTIONS["TRANSFERRED"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # RULE 5: NO_RESPONSE / DELAY — Deemed refusal or administrative delay
    # ═══════════════════════════════════════════════════════════════════════════
    no_response_keywords = [
        r"\bdelay\b",                             # "delay"
        r"administrative\s+reasons",              # "administrative reasons"
        r"deemed\s+refusal",                      # "deemed refusal"
        r"no\s+response",                         # "no response"
    ]
    if any(re.search(p, t) for p in no_response_keywords):
        return {
            "classification": "NO_RESPONSE",
            "confidence": 90.0,
            "summary": "Delay or deemed refusal — no timely response from PIO.",
            "next_step": NEXT_STEP_ACTIONS["NO_RESPONSE"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # DEFAULT FALLBACK: intelligibility check before assuming NO_RESPONSE
    # ═══════════════════════════════════════════════════════════════════════════
    import re as _re
    alpha_chars = len(_re.sub(r'[^a-zA-Z]', '', t))
    total_chars = len(t)
    alpha_ratio = alpha_chars / total_chars if total_chars else 0
    word_count  = len(t.split())

    if word_count < 5 or alpha_ratio < 0.5:
        return {
            "classification": "UNKNOWN",
            "confidence": 0.0,
            "summary": "Input appears to be gibberish or too short to classify.",
            "next_step": "Please provide a valid government RTI response text.",
        }

    return {
        "classification": "NO_RESPONSE",
        "confidence": 55.0,
        "summary": "No clear classification signal found; defaulting to NO_RESPONSE.",
        "next_step": NEXT_STEP_ACTIONS["NO_RESPONSE"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST CASE — Run with: python -m app.agents.response_agent
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Test case from requirements
    test_input = (
        "The requested information is enclosed herewith. "
        "Copies of all documents are attached."
    )
    expected_classification = "ALLOWED"

    result = classify_rti_response(test_input)

    print("=" * 70)
    print("RTI RESPONSE CLASSIFICATION TEST")
    print("=" * 70)
    print(f"Input: {test_input!r}")
    print("-" * 70)
    print(f"Classification: {result['classification']}")
    print(f"Confidence:     {result['confidence']}")
    print(f"Summary:        {result['summary']}")
    print(f"Next Step:      {result['next_step']}")
    print("-" * 70)

    if result["classification"] == expected_classification:
        print("✅ TEST PASSED: Classification is ALLOWED as expected.")
    else:
        print(f"❌ TEST FAILED: Expected {expected_classification}, "
              f"got {result['classification']}")

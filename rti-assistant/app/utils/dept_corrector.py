"""
Department Auto-Corrector — keyword-based + TF-IDF fallback.

auto_correct_department(query, selected_department) returns whether the
selected department is appropriate and suggests alternatives if not.
"""
import re
import math
import logging
from collections import Counter
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword → department mapping
# ---------------------------------------------------------------------------
DEPT_KEYWORD_MAP: Dict[str, List[str]] = {
    "Ministry of Railways": [
        "train", "railway", "rail", "irctc", "ticket", "station", "platform",
        "passenger", "freight", "coach", "locomotive", "reservation",
    ],
    "CBSE": [
        "cbse", "board exam", "class 10", "class 12", "marksheet", "certificate",
        "school", "student", "result", "admit card", "scholarship", "education",
        "migration", "transfer certificate",
    ],
    "EPFO": [
        "pf", "provident fund", "epf", "epfo", "pension", "uan", "esic",
        "employee benefit", "pf balance", "pf withdrawal", "pf claim",
    ],
    "Delhi Police": [
        "police", "fir", "theft", "crime", "complaint", "arrest", "custody",
        "missing", "assault", "investigation", "chargesheet", "security",
        "law and order",
    ],
    "Income Tax Dept": [
        "income tax", "pan", "pan card", "itr", "refund", "tds", "tax return",
        "assessment", "notice", "demand", "challan", "tax deduction", "cbdt",
    ],
    "Passport Office": [
        "passport", "visa", "travel document", "ecr", "emigration", "apostille",
        "police verification", "passport renewal", "tatkal",
    ],
    "AIIMS": [
        "aiims", "hospital", "treatment", "doctor", "patient", "medical",
        "surgery", "clinical", "admission", "health", "medicine", "obd",
        "appointment", "diagnostic",
    ],
    "DDA": [
        "dda", "land", "housing", "flat", "allotment", "registry", "plot",
        "colony", "redevelopment", "construction", "noc", "property", "lease",
        "urban development",
    ],
    "RBI": [
        "rbi", "bank", "banking", "currency", "monetary", "repo rate",
        "inflation", "nbfc", "financial institution", "loan", "interest rate",
        "forex", "foreign exchange",
    ],
    "SEBI": [
        "sebi", "stock", "share", "market", "mutual fund", "nse", "bse",
        "ipo", "demat", "securities", "investor", "broker", "equity", "bond",
        "capital market",
    ],
    "MCD": [
        "mcd", "municipal", "road", "construction", "repair", "contractor",
        "sanitation", "garbage", "water supply", "drainage", "licence",
        "property tax", "building plan", "trade",
    ],
    "BSNL": [
        "bsnl", "telecom", "network", "internet", "broadband", "telephone",
        "landline", "mobile", "sim", "tower", "connectivity", "telecomm",
    ],
    "LIC of India": [
        "lic", "insurance", "policy", "premium", "claim", "maturity",
        "surrender", "nominee", "life insurance", "endowment",
    ],
}

# Flat reverse-lookup: keyword → department (longest match wins)
_KEYWORD_TO_DEPT: Dict[str, str] = {}
for dept, keywords in DEPT_KEYWORD_MAP.items():
    for kw in keywords:
        _KEYWORD_TO_DEPT[kw.lower()] = dept


# ---------------------------------------------------------------------------
# TF-IDF helpers (pure Python, no sklearn dependency)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Lowercase, remove punctuation, split into tokens."""
    return re.findall(r"[a-z]+", text.lower())


def _build_corpus() -> Tuple[List[str], List[List[str]]]:
    """Build a document-per-department corpus from keyword lists."""
    docs, names = [], []
    for dept, keywords in DEPT_KEYWORD_MAP.items():
        # One document per department = all keywords joined
        docs.append(" ".join(keywords))
        names.append(dept)
    return names, [_tokenize(d) for d in docs]


_CORPUS_NAMES, _CORPUS_TOKENS = _build_corpus()
_N_DOCS = len(_CORPUS_NAMES)


def _tfidf_scores(query_tokens: List[str]) -> List[Tuple[str, float]]:
    """
    Compute a simple TF-IDF cosine-like score between the query and each
    department document. Returns list of (dept_name, score) sorted descending.
    """
    # Build IDF: log(N / df) for every unique term in the corpus
    all_terms = set(t for doc in _CORPUS_TOKENS for t in doc)
    idf: Dict[str, float] = {}
    for term in all_terms:
        df = sum(1 for doc in _CORPUS_TOKENS if term in doc)
        idf[term] = math.log((_N_DOCS + 1) / (df + 1)) + 1.0

    def doc_vector(tokens: List[str]) -> Dict[str, float]:
        tf = Counter(tokens)
        return {t: (tf[t] / len(tokens)) * idf.get(t, 1.0) for t in tf}

    query_vec = doc_vector(query_tokens)
    scores = []
    for i, doc_tokens in enumerate(_CORPUS_TOKENS):
        doc_vec = doc_vector(doc_tokens)
        # Dot product (no need to normalise for ranking)
        score = sum(query_vec.get(t, 0) * doc_vec.get(t, 0) for t in query_vec)
        scores.append((_CORPUS_NAMES[i], round(score, 6)))

    return sorted(scores, key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def auto_correct_department(query: str, selected_department: str) -> Dict:
    """
    Analyse `query` and decide whether `selected_department` is appropriate.

    Strategy (layered):
      1. Keyword exact-match → fast and high-confidence.
      2. TF-IDF cosine score over department keyword corpus → handles paraphrasing.
      3. If confidence is low, return top-2 suggestions.

    Args:
        query: The citizen's plain-English information request.
        selected_department: The department chosen in the UI.

    Returns:
        {
            "corrected": bool,
            "suggested_department": str,
            "top_suggestions": list[dict],   # [{dept, score}, ...]
            "confidence": float,             # 0-1
            "message": str,
        }
    """
    query_clean = query.strip().lower()
    tokens = _tokenize(query_clean)

    # ── Layer 1: keyword exact match ────────────────────────────────────────
    keyword_hits: Dict[str, int] = Counter()
    for kw, dept in _KEYWORD_TO_DEPT.items():
        # Match whole-word (longer phrases checked first for specificity)
        pattern = r"\b" + re.escape(kw) + r"\b"
        matches = re.findall(pattern, query_clean)
        if matches:
            keyword_hits[dept] += len(matches)

    if keyword_hits:
        best_kw_dept = max(keyword_hits, key=keyword_hits.get)
        kw_confidence = min(keyword_hits[best_kw_dept] / 3, 1.0)  # 3+ hits → 1.0
    else:
        best_kw_dept = None
        kw_confidence = 0.0

    # ── Layer 2: TF-IDF fallback ─────────────────────────────────────────────
    tfidf = _tfidf_scores(tokens)
    best_tfidf_dept, best_tfidf_score = tfidf[0] if tfidf else (None, 0.0)

    # Normalise TF-IDF score to a 0-1 range (heuristic cap at 0.05 raw → 1.0)
    tfidf_confidence = min(best_tfidf_score / 0.05, 1.0) if best_tfidf_score else 0.0

    # ── Combine layers ───────────────────────────────────────────────────────
    if best_kw_dept and kw_confidence >= 0.33:
        # Keyword match wins — most reliable signal
        predicted = best_kw_dept
        confidence = max(kw_confidence, tfidf_confidence * 0.5)
    elif best_tfidf_dept and tfidf_confidence >= 0.3:
        predicted = best_tfidf_dept
        confidence = tfidf_confidence
    else:
        # No strong signal — trust the user selection
        predicted = selected_department
        confidence = 0.2

    confidence = round(min(confidence, 1.0), 3)

    # ── Build top-2 suggestions (for low-confidence fallback) ────────────────
    seen = set()
    top_suggestions = []
    for dept, score in tfidf[:5]:
        if dept not in seen:
            seen.add(dept)
            top_suggestions.append({"department": dept, "score": round(min(score / 0.05, 1.0), 3)})
        if len(top_suggestions) == 2:
            break

    # ── Compare prediction vs selection ─────────────────────────────────────
    def _normalise(name: str) -> str:
        return name.strip().lower()

    is_correct = _normalise(predicted) == _normalise(selected_department)

    # Log mismatches for future model improvement
    if not is_correct and confidence >= 0.5:
        logger.info(
            "[dept_corrector] Mismatch — selected=%r predicted=%r confidence=%.2f query=%r",
            selected_department, predicted, confidence, query[:120],
        )

    if is_correct or confidence < 0.3:
        return {
            "corrected": False,
            "suggested_department": selected_department,
            "top_suggestions": top_suggestions,
            "confidence": confidence,
            "message": "Selected department is appropriate.",
        }

    # Low-confidence: return top-2 options without forcing a correction
    if confidence < 0.5:
        names = [s["department"] for s in top_suggestions]
        return {
            "corrected": False,
            "suggested_department": selected_department,
            "top_suggestions": top_suggestions,
            "confidence": confidence,
            "message": (
                f"Confidence is low. Possible departments: {', '.join(names)}. "
                "Please verify your selection."
            ),
        }

    # High-confidence mismatch — suggest override
    return {
        "corrected": True,
        "suggested_department": predicted,
        "top_suggestions": top_suggestions,
        "confidence": confidence,
        "message": (
            f"The selected department may be incorrect. "
            f"Suggested department: {predicted}"
        ),
    }

"""Unit tests for the keyword-based RTI response classifier."""
import sys
sys.path.insert(0, "C:\\Assignments\\MOD_8\\rti-assistant")
from app.agents.response_agent import _keyword_fallback_classify

CASES = [
    # (text, expected_category)
    ("Section 8(1)(j) exemption applies, information cannot be disclosed.",     "DENIED"),
    ("Application deemed refusal as no response received within 30 days.",      "NO_RESPONSE"),
    ("Delay in providing information - 30-day period has elapsed.",             "NO_RESPONSE"),
    ("Information not provided within time. Deemed refusal under Section 7(2).","NO_RESPONSE"),
    ("Application transferred under Section 6(3) to Ministry of Finance.",      "TRANSFERRED"),
    ("Some of the records are provided. Remaining documents not available.",     "PARTIAL"),
    ("Partial information furnished. Certain records withheld under exemption.", "DENIED"),
    ("Please find enclosed the information as requested herewith.",              "ALLOWED"),
    ("Details are provided below as per your RTI request.",                      "ALLOWED"),
]

all_pass = True
print("\n  RTI Response Classifier — Unit Tests")
print("  " + "=" * 60)
for text, expected in CASES:
    result = _keyword_fallback_classify(text)
    cat, conf = result["category"], result["confidence"]
    ok = cat == expected
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] Expected={expected:<12} Got={cat:<12} Conf={conf:.0%}  | {text[:52]}...")
    if not ok:
        all_pass = False

print("  " + "=" * 60)
print(f"\n  {'All 9 tests passed!' if all_pass else 'Some tests FAILED.'}\n")
sys.exit(0 if all_pass else 1)

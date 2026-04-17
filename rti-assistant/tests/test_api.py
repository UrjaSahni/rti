"""
RTI Assistant — Full API Test Suite
Covers all 8 FastAPI endpoints:

  GET  /health
  GET  /api/departments
  GET  /api/applications/{email}
  GET  /api/track/{id}
  POST /api/draft-rti
  POST /api/check-rights
  POST /api/parse-response
  POST /api/draft-appeal

Routes are mounted at /api/* (not /api/v1).
Seeded citizen email and app ID are read directly from the DB.
"""
import sys
import sqlite3
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8000"
DB_PATH  = str(Path(__file__).resolve().parent.parent / "rti_tracker.db")

GREEN = "\033[92m"; RED = "\033[91m"; CYAN = "\033[96m"; RESET = "\033[0m"
results: list[tuple[str, bool]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    label = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{label}] {name}")
    if detail:
        print(f"         {detail}")
    results.append((name, passed))


def get_seeded_data() -> tuple[str, int]:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT c.email, a.id FROM citizens c "
        "JOIN rti_applications a ON c.id = a.citizen_id LIMIT 1"
    ).fetchone()
    conn.close()
    return (row[0], row[1]) if row else ("", 1)


# ── Banner ─────────────────────────────────────────────────────────────────────
print(f"\n{CYAN}══════════════════════════════════════════════════════")
print("  RTI Assistant — Full API Test Suite (8 Endpoints)")
print(f"══════════════════════════════════════════════════════{RESET}\n")

seeded_email, seeded_app_id = get_seeded_data()
print(f"  DB seeded email  : {seeded_email}")
print(f"  DB seeded app ID : {seeded_app_id}\n")

# ── TC-1  GET /health ──────────────────────────────────────────────────────────
print(f"{CYAN}[ TC-1 ] GET /health{RESET}")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=30)
    b = r.json()
    api_ok = r.status_code == 200 and b.get("status") == "ok" and b.get("db_ready")
    if api_ok and not b.get("chroma_ready"):
        print(f"  {GREEN}[NOTE]{RESET} chroma_ready=False — run: python scripts/build_rag_index.py")
    check("status=ok, db_ready=true",
          api_ok,
          f"HTTP {r.status_code}  {b}")
except Exception as e:
    check("Health endpoint reachable", False, str(e))

# ── TC-2  GET /api/departments ─────────────────────────────────────────────────
print(f"\n{CYAN}[ TC-2 ] GET /api/departments{RESET}")
try:
    r = requests.get(f"{BASE_URL}/api/departments", timeout=30)
    if r.status_code != 200:
        check("Returns 200", False, f"HTTP {r.status_code}  {r.text[:120]}")
    else:
        depts = r.json()
        ok = isinstance(depts, list) and len(depts) > 0
        required = {"id", "name", "ministry", "pio_name"}
        fields_ok = ok and required.issubset(depts[0].keys())
        check(f"Returns list of {len(depts)} depts with id/name/ministry/pio_name",
              fields_ok,
              f"Sample: {depts[0].get('name')} — {depts[0].get('ministry')}")
except Exception as e:
    check("Departments endpoint reachable", False, str(e))

# ── TC-3  GET /api/applications/{email} ───────────────────────────────────────
print(f"\n{CYAN}[ TC-3 ] GET /api/applications/{{email}}{RESET}")
try:
    r = requests.get(f"{BASE_URL}/api/applications/{seeded_email}", timeout=30)
    if r.status_code != 200:
        check("Returns 200", False, f"HTTP {r.status_code}  {r.text[:120]}")
    else:
        apps = r.json()
        ok   = isinstance(apps, list) and len(apps) > 0
        required = {"application_id", "application_number", "status",
                    "department", "date_filed", "deadline_date", "is_overdue"}
        fields_ok = ok and required.issubset(apps[0].keys())
        check(f"Returns {len(apps)} app(s) with all required fields",
              fields_ok,
              f"First app#: {apps[0].get('application_number')} | "
              f"Status: {apps[0].get('status')} | Overdue: {apps[0].get('is_overdue')}")
except Exception as e:
    check("Applications-by-email endpoint reachable", False, str(e))

# ── TC-4  GET /api/applications/{email} — unknown email → empty list ──────────
print(f"\n{CYAN}[ TC-4 ] GET /api/applications/{{unknown_email}} — empty list{RESET}")
try:
    r = requests.get(f"{BASE_URL}/api/applications/nobody@nowhere.com", timeout=30)
    ok = r.status_code == 200 and r.json() == []
    check("Returns 200 with empty list for unknown email",
          ok, f"HTTP {r.status_code}  body={r.json()}")
except Exception as e:
    check("Unknown-email returns empty list", False, str(e))

# ── TC-5  GET /api/track/{id} ─────────────────────────────────────────────────
print(f"\n{CYAN}[ TC-5 ] GET /api/track/{seeded_app_id}{RESET}")
try:
    r = requests.get(f"{BASE_URL}/api/track/{seeded_app_id}", timeout=30)
    if r.status_code != 200:
        check("Returns 200 with tracking data", False,
              f"HTTP {r.status_code}  {r.text[:120]}")
    else:
        b = r.json()
        required = {"application_number", "subject", "department", "status",
                    "date_filed", "deadline_date", "days_remaining", "is_overdue", "timeline"}
        ok = required.issubset(b.keys()) and isinstance(b["timeline"], list)
        check("Response has all tracking fields + timeline list",
              ok,
              f"App# {b.get('application_number')} | Status: {b.get('status')} | "
              f"Deadline: {b.get('deadline_date')} | Days left: {b.get('days_remaining')} | "
              f"Timeline events: {len(b.get('timeline', []))}")
except Exception as e:
    check("Track endpoint reachable", False, str(e))

# ── TC-6  GET /api/track/999999 — 404 ─────────────────────────────────────────
print(f"\n{CYAN}[ TC-6 ] GET /api/track/999999 — not found{RESET}")
try:
    r = requests.get(f"{BASE_URL}/api/track/999999", timeout=30)
    ok = r.status_code == 404
    check("Returns 404 for non-existent application ID",
          ok, f"HTTP {r.status_code}  {r.json()}")
except Exception as e:
    check("Track 404 test", False, str(e))

# ── TC-7  POST /api/draft-rti — validation error (missing fields) ──────────────
print(f"\n{CYAN}[ TC-7 ] POST /api/draft-rti — missing required fields → 422{RESET}")
try:
    r = requests.post(f"{BASE_URL}/api/draft-rti",
                      json={"department_name": "EPFO",
                            "citizen_request": "Status of my pension claim."},
                      timeout=15)
    ok = r.status_code == 422
    detail = r.json().get("detail", [])
    missing = [e["loc"][-1] for e in detail if isinstance(e, dict) and "loc" in e]
    check("Returns 422 for missing citizen_name / citizen_address / citizen_email",
          ok, f"HTTP {r.status_code} | Missing: {missing}")
except Exception as e:
    check("POST /api/draft-rti validation", False, str(e))

# ── TC-8  POST /api/check-rights ──────────────────────────────────────────────
print(f"\n{CYAN}[ TC-8 ] POST /api/check-rights{RESET}")
try:
    r = requests.post(f"{BASE_URL}/api/check-rights",
                      json={"question": "What is the time limit for PIO to respond?"},
                      timeout=60)
    if r.status_code != 200:
        check("Returns 200 with RAG answer", False,
              f"HTTP {r.status_code}  {r.text[:200]}")
    else:
        b = r.json()
        required = {"answer", "source_sections", "case_precedents", "confidence"}
        ok = required.issubset(b.keys()) and len(b.get("answer", "")) > 20
        check("Returns answer, source_sections, case_precedents, confidence",
              ok,
              f"Confidence: {b.get('confidence')} | "
              f"Sections: {b.get('source_sections')} | "
              f"Answer[:80]: {b.get('answer','')[:80]}...")
except Exception as e:
    check("POST /api/check-rights", False, str(e))

# ── TC-9  POST /api/parse-response — missing body → 400 ──────────────────────
print(f"\n{CYAN}[ TC-9 ] POST /api/parse-response — no text/pdf → 400{RESET}")
try:
    r = requests.post(f"{BASE_URL}/api/parse-response",
                      data={},
                      timeout=15)
    ok = r.status_code == 400
    check("Returns 400 when neither text nor PDF provided",
          ok, f"HTTP {r.status_code}  {r.json()}")
except Exception as e:
    check("POST /api/parse-response validation", False, str(e))

# ── TC-10  POST /api/parse-response — with text ────────────────────────────────
print(f"\n{CYAN}[ TC-10 ] POST /api/parse-response — with response_text{RESET}")
try:
    r = requests.post(
        f"{BASE_URL}/api/parse-response",
        data={
            "response_text": (
                "Your RTI application has been examined. The information requested "
                "is exempt under Section 8(1)(a) of the RTI Act and is therefore denied."
            ),
        },
        timeout=60,
    )
    if r.status_code != 200:
        check("Returns 200 with classification", False,
              f"HTTP {r.status_code}  {r.text[:200]}")
    else:
        b = r.json()
        required = {"classification", "confidence", "summary", "recommended_action", "raw_text"}
        ok = required.issubset(b.keys())
        check("Returns classification, confidence, summary, recommended_action, raw_text",
              ok,
              f"Classification: {b.get('classification')} | "
              f"Confidence: {b.get('confidence'):.2f} | "
              f"Action: {b.get('recommended_action', '')[:60]}")
except Exception as e:
    check("POST /api/parse-response with text", False, str(e))

# ── TC-11  POST /api/draft-appeal — with response_text + classification ──────
print(f"\n{CYAN}[ TC-11 ] POST /api/draft-appeal — with response_text + classification{RESET}")
try:
    r = requests.post(
        f"{BASE_URL}/api/draft-appeal",
        json={
            "response_text": "Your RTI application is denied under Section 8(1)(a).",
            "classification": "DENIED",
            "appellant_name": "Test User",
            "appellant_address": "123 Test Street, Test City",
        },
        timeout=60,
    )
    if r.status_code != 200:
        check("Returns 200 with appeal draft", False,
              f"HTTP {r.status_code}  {r.text[:200]}")
    else:
        b = r.json()
        required = {"appeal_text", "grounds", "appeal_authority", "deadline_to_file", "legal_basis"}
        ok = required.issubset(b.keys()) and len(b.get("appeal_text", "")) > 100
        check("Returns appeal_text, grounds, appeal_authority, deadline_to_file, legal_basis",
              ok,
              f"Appeal Authority: {b.get('appeal_authority')} | "
              f"Deadline: {b.get('deadline_to_file')} | "
              f"Appeal text length: {len(b.get('appeal_text', ''))}")
except Exception as e:
    check("POST /api/draft-appeal", False, str(e))

# ── Summary ────────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total  = len(results)
color  = GREEN if passed == total else RED
print(f"\n{CYAN}══════════════════════════════════════════════════════{RESET}")
print(f"  Results: {color}{passed}/{total} tests passed{RESET}")
print(f"{CYAN}══════════════════════════════════════════════════════{RESET}\n")
if __name__ == "__main__" and passed < total:
    sys.exit(1)

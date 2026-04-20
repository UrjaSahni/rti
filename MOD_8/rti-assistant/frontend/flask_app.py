"""
Flask frontend for the RTI Query Assistant.

5 pages via navigation:
  1. File RTI Application
  2. Know Your Rights
  3. Track My RTIs
  4. Parse Government Response
  5. Draft Appeal Letter
"""
import io
import os
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rti-assistant-secret-key-2024")

# API Base URL - when mounted under FastAPI, use localhost
# When running standalone, use environment variable
API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api")


# ── PDF generation helper ───────────────────────────────────────────────────────
def generate_pdf_bytes(text: str, title: str = "RTI Document") -> bytes:
    """Generate a PDF from plain text using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_LEFT

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2.5*cm, rightMargin=2.5*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "body", parent=styles["Normal"],
            fontSize=11, leading=16, alignment=TA_LEFT,
        )
        title_style = ParagraphStyle(
            "title", parent=styles["Heading1"],
            fontSize=14, spaceAfter=12,
        )
        story = [
            Paragraph(title, title_style),
            Spacer(1, 0.3*cm),
        ]
        for line in text.split("\n"):
            para_text = line.strip() if line.strip() else "&nbsp;"
            story.append(Paragraph(para_text, body_style))
            story.append(Spacer(1, 0.15*cm))
        doc.build(story)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        return f"PDF generation failed: {e}".encode()


# ── API helpers ─────────────────────────────────────────────────────────────────
def api_get(endpoint: str, **kwargs):
    """Make a GET request to the API."""
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=30, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "API is offline. Please start the FastAPI server."
    except requests.exceptions.HTTPError as e:
        return None, f"API error: {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def api_post(endpoint: str, **kwargs):
    """Make a POST request to the API."""
    try:
        r = requests.post(f"{API_BASE}{endpoint}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "API is offline. Please start the FastAPI server."
    except requests.exceptions.HTTPError as e:
        return None, f"API error: {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def markdown_to_html(text: str) -> str:
    """Convert simple markdown to HTML for display."""
    if not text:
        return text

    # Escape HTML first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Convert **bold** to <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    lines = text.split('\n')
    result = []
    in_ol = False
    in_ul = False

    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            continue

        # Numbered list: "1. item"
        numbered_match = re.match(r'^(\d+)\.\s+(.+)', stripped)
        # Bullet: "- item" or "• item"
        bullet_match = re.match(r'^[-•]\s+(.+)', stripped)
        # Bold-title item: "<strong>Title</strong>: description"
        bold_title_match = re.match(r'^<strong>([^<]+)</strong>:\s*(.*)$', stripped)

        if numbered_match or bold_title_match:
            # Both numbered and bold-title items go into an <ol> for consistent numbering
            if not in_ol:
                if in_ul:
                    result.append('</ul>')
                    in_ul = False
                result.append('<ol class="mb-3">')
                in_ol = True
            if numbered_match:
                result.append(f'<li>{numbered_match.group(2)}</li>')
            else:
                title = bold_title_match.group(1)
                desc = bold_title_match.group(2)
                result.append(f'<li><strong>{title}:</strong> {desc}</li>')
        elif bullet_match:
            if not in_ul:
                if in_ol:
                    result.append('</ol>')
                    in_ol = False
                result.append('<ul class="mb-3">')
                in_ul = True
            result.append(f'<li>{bullet_match.group(1)}</li>')
        else:
            if in_ol:
                result.append('</ol>')
                in_ol = False
            if in_ul:
                result.append('</ul>')
                in_ul = False
            if stripped:
                result.append(f'<p>{stripped}</p>')

    if in_ol:
        result.append('</ol>')
    if in_ul:
        result.append('</ul>')

    return '\n'.join(result)


def get_departments():
    """Fetch list of department names from the API."""
    data, _ = api_get("/departments")
    if data:
        return [d["name"] for d in data]
    return [
        "Ministry of Railways", "CBSE", "EPFO", "Delhi Police",
        "Income Tax Dept", "Passport Office", "AIIMS", "DDA",
        "RBI", "SEBI", "MCD", "BSNL", "LIC of India",
    ]


# ── Routes ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Home page - File RTI Application."""
    departments = get_departments()
    return render_template("index.html", departments=departments, page="file_rti")


@app.route("/file-rti", methods=["GET", "POST"])
def file_rti():
    """Page 1: File RTI Application."""
    departments = get_departments()
    result = None
    error = None
    dept_warning = None

    if request.method == "POST":
        citizen_name = request.form.get("citizen_name", "").strip()
        citizen_email = request.form.get("citizen_email", "").strip()
        citizen_address = request.form.get("citizen_address", "").strip()
        citizen_request = request.form.get("citizen_request", "").strip()
        department = request.form.get("department", "")
        is_bpl = request.form.get("is_bpl") == "on"

        if not all([citizen_name, citizen_email, citizen_address, citizen_request]):
            error = "Please fill in all required fields."
        else:
            # Check department match
            dept_check, _ = api_post("/check-department", json={
                "query": citizen_request,
                "selected_department": department
            })
            if dept_check and dept_check.get("corrected"):
                dept_warning = {
                    "suggested": dept_check["suggested_department"],
                    "confidence": dept_check.get("confidence", 0),
                    "message": dept_check.get("message", "")
                }

            # Generate RTI application
            response, err = api_post("/draft-rti", json={
                "citizen_request": citizen_request,
                "department_name": department,
                "citizen_name": citizen_name,
                "citizen_address": citizen_address,
                "citizen_email": citizen_email,
                "is_bpl": is_bpl,
            })

            if err:
                error = err
            elif response:
                result = response
                # Convert instructions to HTML with proper line breaks
                if result.get("instructions"):
                    result["instructions"] = markdown_to_html(result["instructions"])

    return render_template("file_rti.html",
                           departments=departments,
                           result=result,
                           error=error,
                           dept_warning=dept_warning,
                           page="file_rti")


@app.route("/know-your-rights", methods=["GET", "POST"])
def know_your_rights():
    """Page 2: Know Your Rights."""
    result = None
    error = None
    question = ""

    example_questions = [
        "What is the deadline for RTI response?",
        "Can BPL citizens file RTI for free?",
        "What happens if the PIO does not respond?",
        "What information is exempt under RTI?",
        "How do I file a first appeal?",
    ]

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if not question:
            error = "Please enter a question."
        else:
            response, err = api_post("/check-rights", json={"question": question})
            if err:
                error = err
            elif response:
                result = response
                # Convert markdown answer to HTML for display
                if result.get("answer"):
                    result["answer"] = markdown_to_html(result["answer"])

    return render_template("know_your_rights.html",
                           result=result,
                           error=error,
                           question=question,
                           example_questions=example_questions,
                           page="know_your_rights")


@app.route("/track-rti", methods=["GET", "POST"])
def track_rti():
    """Page 3: Track My RTIs."""
    applications = None
    error = None
    email = ""
    top_filers = []

    # Get top filers for quick pick
    filers_data, _ = api_get("/top-filers?limit=10")
    if filers_data:
        top_filers = filers_data

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            error = "Please enter your email address."
        else:
            data, err = api_get(f"/applications/{email}")
            if err:
                error = err
            elif data is not None:
                if not data:
                    error = f"No RTI applications found for {email}."
                else:
                    applications = data

    return render_template("track_rti.html",
                           applications=applications,
                           error=error,
                           email=email,
                           top_filers=top_filers,
                           page="track_rti")


@app.route("/parse-response", methods=["GET", "POST"])
def parse_response():
    """Page 4: Parse Government Response."""
    result = None
    error = None
    warning = None

    if request.method == "POST":
        response_text = request.form.get("response_text", "").strip()
        pdf_file = request.files.get("pdf_file")
        has_file = pdf_file and pdf_file.filename

        if not has_file and not response_text:
            error = "Please upload a file or paste response text — at least one input is required."
        else:
            # Show warning if both inputs provided
            if has_file and response_text:
                warning = "Both PDF and text provided. Using text input for analysis."
            
            try:
                files = None
                data = {}

                # Prioritize text input over file
                if response_text:
                    data["response_text"] = response_text
                elif has_file:
                    files = {"pdf_file": (pdf_file.filename, pdf_file.read(), "application/pdf")}

                r = requests.post(
                    f"{API_BASE}/parse-response",
                    data=data,
                    files=files,
                    timeout=60,
                )
                r.raise_for_status()
                result = r.json()

                # Store analysis result in session for appeal page
                # Only store if classification is actionable — not UNKNOWN (gibberish input)
                if result.get("classification") not in ("UNKNOWN", None):
                    session["analysis_result"] = {
                        "raw_text": result.get("raw_text", response_text or ""),
                        "classification": result.get("classification", "DENIED"),
                        "summary": result.get("summary", ""),
                    }
                else:
                    session.pop("analysis_result", None)  # Clear any stale session data
            except requests.exceptions.ConnectionError:
                error = "API is offline. Please start the FastAPI server."
            except Exception as e:
                error = str(e)

    return render_template("parse_response.html",
                           result=result,
                           error=error,
                           warning=warning,
                           page="parse_response")


@app.route("/draft-appeal", methods=["GET", "POST"])
def draft_appeal():
    """Page 5: Draft Appeal Letter."""
    result = None
    error = None
    
    # Check for stored analysis result
    analysis_result = session.get("analysis_result")
    default_text = analysis_result.get("raw_text", "") if analysis_result else ""
    default_class = analysis_result.get("classification", "DENIED") if analysis_result else "DENIED"

    classification_options = ["DENIED", "PARTIAL", "NO_RESPONSE", "TRANSFERRED", "ALLOWED"]

    if request.method == "POST":
        response_text = request.form.get("response_text", "").strip()
        classification = request.form.get("classification", "DENIED")
        appellant_name = request.form.get("appellant_name", "").strip() or None
        appellant_address = request.form.get("appellant_address", "").strip() or None
        department_name = request.form.get("department_name", "").strip() or None
        rti_subject = request.form.get("rti_subject", "").strip() or None
        date_filed = request.form.get("date_filed", "").strip() or None

        if not response_text:
            error = "Please provide the government response text."
        else:
            response, err = api_post("/draft-appeal", json={
                "response_text": response_text,
                "classification": classification,
                "appellant_name": appellant_name,
                "appellant_address": appellant_address,
                "department_name": department_name,
                "rti_subject": rti_subject,
                "date_filed": date_filed,
            })

            if err:
                error = err
            elif response:
                result = response

    return render_template("draft_appeal.html",
                           result=result,
                           error=error,
                           default_text=default_text,
                           default_class=default_class,
                           classification_options=classification_options,
                           has_analysis=analysis_result is not None,
                           now=datetime.now(),
                           page="draft_appeal")


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    """Generate and download PDF."""
    text = request.form.get("text", "")
    title = request.form.get("title", "RTI Document")
    filename = request.form.get("filename", "document.pdf")

    pdf_bytes = generate_pdf_bytes(text, title)
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@app.route("/clear-session", methods=["POST"])
def clear_session():
    """Clear analysis result from session."""
    session.pop("analysis_result", None)
    return jsonify({"status": "cleared"})


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "flask-frontend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

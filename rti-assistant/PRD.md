# Product Requirements Document (PRD)
## RTI Query Assistant & Document Tracker

**Version:** 2.2.0  
**Last Updated:** April 2026  
**Status:** Production-Ready — All P0/P1 features implemented, tested, and containerised

---

## 1. Executive Summary

### 1.1 Product Vision
The RTI Query Assistant is an AI-powered citizen-facing application designed to democratize access to India's Right to Information Act, 2005. It enables citizens to exercise their fundamental right to information without requiring legal expertise or navigating complex bureaucratic processes.

### 1.2 Problem Statement
Indian citizens face significant barriers when filing RTI applications:
- **Complexity**: The RTI Act has 31 sections with specific procedural requirements
- **Legal Language**: Government responses are often difficult to interpret
- **Deadline Management**: Multiple time-sensitive deadlines (30 days for response, 30 days for first appeal, 90 days for second appeal)
- **Appeal Process**: Citizens don't know how to draft legally compliant appeal letters when applications are denied

### 1.3 Solution
A comprehensive AI assistant that:
1. **Drafts RTI Applications** from plain English queries
2. **Answers RTI-Related Questions** using RAG over the RTI Act
3. **Parses Government Responses** and classifies outcomes
4. **Tracks Deadlines** and sends reminders
5. **Auto-Drafts Appeal Letters** when applications are denied or not responded to

---

## 2. Target Users

### 2.1 Primary Users
- **Indian Citizens** seeking government information
- **Journalists and Researchers** filing bulk RTI requests
- **NGOs and Activists** monitoring government transparency
- **Legal Aid Organizations** assisting citizens with RTI

### 2.2 User Personas

**Persona 1: Concerned Citizen (Rajesh, 45)**
- Wants to know why his building permit was delayed
- No legal background
- Needs simple language explanations
- Pain point: Doesn't know how to frame an RTI request

**Persona 2: Investigative Journalist (Priya, 32)**
- Files multiple RTI requests monthly
- Needs to track responses across departments
- Pain point: Managing deadlines for 20+ active RTIs

**Persona 3: First-Time Filer (Amit, 28)**
- Received a denial letter, doesn't understand why
- Wants to appeal but doesn't know the process
- Pain point: Legal jargon in government responses

---

## 3. Features & Requirements

### 3.1 Core Features

#### Feature 1: RTI Application Drafting
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P0 (Must Have) |
| **Input** | Plain English query + Department name |
| **Output** | Formatted RTI application with all legal requirements |
| **Format** | Strict formal letter format with proper sections |
| **Validation** | Must include applicant details placeholder, RTI fee reference, Section 6(1) citation |

**Acceptance Criteria:**
- [x] Generated draft includes "Subject:", "To:", date, and signature block
- [x] Uses generic PIO designation (not fabricated names)
- [x] Includes mandatory disclaimer: "This is an AI-generated draft"
- [x] Cites relevant RTI Act sections correctly (1-31 only)
- [x] PDF download option available
- [x] **NEW:** Auto-detects department mismatch via `/api/check-department` (keyword + TF-IDF)
- [x] **NEW:** Backend auto-corrects department if high-confidence mismatch detected
- [x] **NEW:** Input validation (gibberish detection) on all text inputs before LLM call
- [x] **NEW:** Next Steps displayed as formatted numbered list (not inline text)

#### Feature 2: RTI Rights Q&A (RAG)
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P0 (Must Have) |
| **Knowledge Base** | RTI Act 2005 (31 sections) + CIC case orders |
| **Architecture** | 4-layer: Rule-based → Section mapping → RAG → Fallback |
| **Response Time** | < 5 seconds |

**Acceptance Criteria:**
- [x] Correctly answers questions about time limits (30 days, 90 days)
- [x] Never says "not covered by RTI Act" for valid queries
- [x] Cites specific section numbers when relevant
- [x] Handles synonyms (e.g., "second appeal" = "CIC appeal")

#### Feature 3: Government Response Classification
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P0 (Must Have) |
| **Input** | PDF upload OR plain text |
| **Classifications** | ALLOWED, PARTIAL, DENIED, TRANSFERRED, NO_RESPONSE |
| **Output** | Classification + confidence + summary + recommended action |

**Acceptance Criteria:**
- [x] **ALLOWED has highest priority** — phrases like "information enclosed" always return ALLOWED, not NO_RESPONSE
- [x] Correctly identifies "deemed refusal" as NO_RESPONSE (not DENIED)
- [x] Confidence score provided (0–1.0 scale)
- [x] Actionable recommendations based on classification
- [x] Returns raw text for use in appeal generation
- [x] Standalone `classify_rti_response(text)` function with priority-ordered rules
- [x] **NEW v2.2:** Gibberish / too-short input returns `UNKNOWN` classification — LLM call skipped entirely
- [x] **NEW v2.2:** `UNKNOWN` displayed as a red error alert in the UI; not saved to session

#### Feature 4: Appeal Letter Generation
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P0 (Must Have) |
| **Input** | Response text + Classification + Optional user details |
| **Output** | Conditional: `no_appeal` (ALLOWED) or `appeal_letter` (all others) |
| **No Database Dependency** | Works with just the response text |

**Acceptance Criteria:**
- [x] **ALLOWED** → returns `{type: "no_appeal", message, suggestion}` — NO letter generated
- [x] **PARTIAL** → appeal citing incomplete info, Section 7(1), 19(8)(b)
- [x] **NO_RESPONSE** → appeal citing deemed refusal, Section 7(2), Section 20 penalty
- [x] **DENIED/REJECTED** → appeal challenging improper Section 8/9 exemptions, Section 10 severability
- [x] **TRANSFERRED** → appeal citing non-response from transferee department
- [x] Uses user-provided name/address OR placeholders like [Your Name]
- [x] Dynamic insertion: applicant name, dept, RTI subject, date filed all auto-populated
- [x] Deadline auto-calculated (today + 30 days) and shown as UI alert
- [x] PDF download via reportlab
- [x] **NEW v2.2:** Removed `Note:` footer from letter body — it is shown as a UI alert instead

#### Feature 5: Application Tracking
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P1 (Should Have) |
| **Deadlines Tracked** | Initial response (30 days), First appeal (30 days), Second appeal (90 days) |
| **Status Updates** | SUBMITTED, RESPONDED, APPEALED, RESOLVED, OVERDUE |

**Acceptance Criteria:**
- [x] Calculates correct deadlines from submission date
- [x] Timeline view of application history with progress bar
- [x] Case-insensitive email lookup
- [x] **NEW:** `/api/top-filers` endpoint returns top N citizens by app count
- [x] **NEW:** Quick-pick buttons in Track page for seeded email addresses

#### Feature 6: Department Auto-Correction *(NEW in v2)*
| Attribute | Specification |
|-----------|---------------|
| **Priority** | P1 (Should Have) |
| **Input** | Query text + selected department |
| **Output** | Corrected department + confidence + top suggestions |

**Acceptance Criteria:**
- [x] Layer 1: keyword whole-word regex match across 13 departments
- [x] Layer 2: pure-Python TF-IDF cosine similarity (no ML dependency)
- [x] Confidence ≥ 0.5 triggers auto-correction
- [x] Confidence < 0.3 returns low-confidence hint with top-2 alternatives
- [x] UI shows warning banner on mismatch, info banner on low-confidence

### 3.2 Non-Functional Requirements

#### Performance
| Metric | Target |
|--------|--------|
| API Response Time | < 3 seconds (95th percentile) |
| Concurrent Users | 100 simultaneous |
| LLM Fallback | Automatic failover from Groq to OpenAI |

#### Reliability
| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| Error Rate | < 1% of requests |
| Data Persistence | SQLite with WAL mode |

#### Security
| Requirement | Implementation |
|-------------|----------------|
| Data Privacy | No PII stored without consent |
| API Keys | Environment variables only |
| CORS | Configurable origin whitelist |

---

## 4. Technical Architecture

### 4.1 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Flask + Bootstrap)                  │
│  5 Pages: Draft RTI | Rights Q&A | Track | Parse | Appeal        │
│  Mounted at /ui via WSGIMiddleware                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│  Routes: /api/draft-rti, /api/check-rights, /api/parse-response │
│          /api/track/{id}, /api/draft-appeal, /api/departments   │
└──────────┬─────────────────────────────────────┬────────────────┘
           │                                     │
┌──────────▼──────────┐              ┌───────────▼───────────────┐
│  AGENT ORCHESTRATOR │              │  RAG PIPELINE              │
│  (LangGraph)        │              │  ChromaDB + MiniLM-L6-v2   │
│  - Intent Classifier│              │  - rti_act_chunks          │
│  - Draft Agent      │              │  - rti_case_chunks         │
│  - RAG Agent        │◄─────────────┤  + Rule-based KB           │
│  - Response Agent   │              └───────────────────────────┘
│  - Appeal Agent     │
│  - Track Agent      │
└──────────┬──────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  LLM LAYER                                                       │
│  Primary: Groq llama-3.3-70b-versatile                          │
│  Fallback: OpenAI gpt-4o-mini                                   │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  DATABASE (SQLite)                                               │
│  Tables: Citizens, Departments, RTIApplications,                 │
│          GovernmentResponses, Appeals, AuditLog                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| Frontend | Flask + Bootstrap 5 | Production-ready, lightweight, responsive |
| Backend | FastAPI | Async, auto-docs, Pydantic validation |
| Agent Framework | LangGraph | Stateful multi-agent orchestration |
| Vector DB | ChromaDB | Lightweight, embedded, Python-native |
| Embeddings | all-MiniLM-L6-v2 | Fast, accurate, local (no API cost) |
| Primary LLM | Groq (Llama 3.3 70B) | Free tier, fast inference |
| Fallback LLM | OpenAI (GPT-4o-mini) | Reliable, better at structured output |
| Database | SQLite | Zero-config, portable, sufficient for single-server |
| PDF Generation | ReportLab | Pure Python PDF creation |
| PDF Parsing | pdfplumber + PyMuPDF | Text extraction from government response PDFs |
| ML / Fine-tuning | Transformers + PyTorch | DistilBERT classifier training (scripts only) |

### 4.3 Data Models

#### RTIApplication
```python
class RTIApplication:
    id: int                     # Primary key
    citizen_id: int             # Foreign key to Citizens
    department_id: int          # Foreign key to Departments
    subject: str                # RTI subject line
    information_sought: str     # Detailed query
    status: ApplicationStatus   # SUBMITTED, PENDING, RESPONDED, APPEALED, CLOSED
    submission_date: date       # When filed
    deadline_date: date         # 30 days from submission
    fee_paid: float            # Usually ₹10
    created_at: datetime
    updated_at: datetime
```

#### ClassificationResult
```python
class ClassificationResult:
    classification: str    # GRANTED, PARTIALLY_GRANTED, DENIED, TRANSFERRED, NO_RESPONSE
    confidence: float      # 0.0 - 1.0
    summary: str          # Human-readable summary of response
    recommended_action: str # What the citizen should do next
    raw_text: str         # Extracted text for appeal generation
```

---

## 5. API Specification

### 5.1 Endpoints

#### POST /api/draft-rti
**Purpose:** Generate a formal RTI application from plain English

**Request:**
```json
{
  "citizen_request": "I want to know how many potholes were reported in my ward",
  "department_name": "Municipal Corporation",
  "citizen_name": "Rajesh Kumar",
  "citizen_address": "123 Main Street, Mumbai",
  "citizen_email": "rajesh@example.com"
}
```

**Response:**
```json
{
  "draft": "To,\nThe Public Information Officer (PIO)...",
  "department_pio_details": "Municipal Corporation, Mumbai",
  "estimated_fee": 10,
  "deadline_info": "Response expected within 30 days of submission",
  "application_id": 301
}
```

#### POST /api/check-rights
**Purpose:** Answer RTI-related questions using RAG

**Request:**
```json
{
  "question": "What is the time limit for filing a second appeal?"
}
```

**Response:**
```json
{
  "answer": "Under Section 19(3) of the RTI Act, 2005, a second appeal must be filed with the Central Information Commission (CIC) or State Information Commission (SIC) within 90 days from the date of the first appellate authority's decision.",
  "sources": ["Section 19(3) - Appeals"],
  "confidence": 0.95
}
```

#### POST /api/parse-response
**Purpose:** Classify a government RTI response

**Request (JSON):**
```json
{
  "response_text": "Your RTI application dated 01/01/2025 is hereby rejected under Section 8(1)(d) as it relates to commercial confidence."
}
```

**Request (Multipart):**
```
POST /api/parse-response
Content-Type: multipart/form-data
file: <PDF file>
```

**Response:**
```json
{
  "classification": "DENIED",
  "confidence": 0.92,
  "summary": "The PIO denied the request citing Section 8(1)(d) regarding commercial confidence.",
  "recommended_action": "You may file a first appeal under Section 19(1) within 30 days.",
  "raw_text": "Your RTI application dated..."
}
```

#### POST /api/draft-appeal
**Purpose:** Generate a first appeal letter

**Request:**
```json
{
  "response_text": "Your RTI application dated 01/01/2025 is hereby rejected...",
  "classification": "DENIED",
  "appellant_name": "Rajesh Kumar",
  "appellant_address": "123 Main Street, Mumbai",
  "department_name": "Municipal Corporation"
}
```

**Response:**
```json
{
  "appeal_letter": "To,\nThe First Appellate Authority...",
  "deadline": "30 days from receipt of denial",
  "filing_instructions": "Submit to the designated FAA with ₹0 fee"
}
```

---

## 6. Evaluation Framework

### 6.1 Quality Metrics

| Component | Metric | Target | Method |
|-----------|--------|--------|--------|
| RTI Draft | Completeness Score | ≥ 0.83 | Checklist validation (8 required elements) |
| RAG Q&A | Accuracy | ≥ 0.70 | Golden Q&A pairs (20 questions) |
| Classifier | F1 Score | ≥ 0.70 | Test set evaluation |
| Deadline Tracker | Unit Tests | 100% pass | 10 test cases |
| End-to-End | Scenario Pass Rate | ≥ 80% | 5 user journey tests |
| Ethics | Hallucination Rate | < 5% | Section number validation |
| Ethics | Disclaimer Present | ≥ 90% | Output scanning |

### 6.2 Test Scenarios

1. **Happy Path**: File RTI → Receive response → Mark as granted
2. **Denial Flow**: File RTI → Receive denial → Draft appeal
3. **Deemed Refusal**: File RTI → No response after 30 days → Flag as NO_RESPONSE
4. **Transfer**: RTI transferred to another department → Update tracking
5. **Rights Query**: Ask about second appeal timeline → Receive correct answer (90 days)

---

## 7. Ethics & Safety

### 7.1 Guardrails

| Risk | Mitigation |
|------|------------|
| Hallucinated Section Numbers | Regex validation: sections must be 1-31 |
| Fabricated PIO Names | Always use generic designation |
| Missing Disclaimer | Enforced in prompt template AND validated |
| Bias in Classification | Monitor accuracy across department groups |
| Over-reliance on AI | Clear warning that this is AI-generated |

### 7.2 Data Privacy

- No citizen PII stored without explicit consent
- API keys stored in environment variables only
- No logging of personal information
- GDPR-compliant data handling principles

---

## 8. Deployment

### 8.1 Local Development
```bash
python setup.py                           # One-click setup
uvicorn app.main:app --reload            # Start API (Flask UI at /ui)
```

**Access Points:**
- API Docs: http://localhost:8000/docs
- Flask UI: http://localhost:8000/ui/
- Health: http://localhost:8000/health

### 8.2 Docker — Local
```bash
# Build and run via docker-compose
docker-compose up --build

# OR build manually
docker build -t rti-assistant:latest .
docker run -d -p 8000:8000 --env-file .env \
  -v $(pwd)/chroma_store:/app/chroma_store \
  -v $(pwd)/rti_tracker.db:/app/rti_tracker.db \
  rti-assistant:latest
```

### 8.3 Azure App Service — Container Deployment

#### Prerequisites
- Azure CLI + Docker Desktop installed
- Azure subscription

#### Step 1 — Create Azure Resources
```bash
az login
az group create --name rti-assistant-rg --location eastus
az acr create --resource-group rti-assistant-rg \
  --name rtiassistantacr --sku Basic --admin-enabled true
```

#### Step 2 — Build & Push Image to ACR
```bash
docker build -f Dockerfile.azure -t rti-assistant:latest .
docker tag rti-assistant:latest rtiassistantacr.azurecr.io/rti-assistant:latest
az acr login --name rtiassistantacr
docker push rtiassistantacr.azurecr.io/rti-assistant:latest
```

#### Step 3 — Create App Service
```bash
az appservice plan create --name rti-assistant-plan \
  --resource-group rti-assistant-rg --sku B1 --is-linux

ACR_PASSWORD=$(az acr credential show --name rtiassistantacr \
  --query "passwords[0].value" -o tsv)

az webapp create \
  --resource-group rti-assistant-rg \
  --plan rti-assistant-plan \
  --name rti-assistant-app \
  --deployment-container-image-name rtiassistantacr.azurecr.io/rti-assistant:latest \
  --docker-registry-server-url https://rtiassistantacr.azurecr.io \
  --docker-registry-server-user rtiassistantacr \
  --docker-registry-server-password $ACR_PASSWORD
```

#### Step 4 — Configure Environment Variables
```bash
az webapp config appsettings set \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app \
  --settings \
    GROQ_API_KEY="your-groq-api-key" \
    OPENAI_API_KEY="your-openai-api-key" \
    SECRET_KEY="your-secret-key" \
    PYTHONPATH="/app" \
    WEBSITES_PORT=8000
```

#### Step 5 — Verify
```bash
az webapp show --resource-group rti-assistant-rg \
  --name rti-assistant-app --query defaultHostName -o tsv

az webapp log tail --resource-group rti-assistant-rg --name rti-assistant-app
```

**Live URL:** `https://rti-assistant-app.azurewebsites.net`

| Endpoint | URL |
|----------|-----|
| Flask UI | `/ui/` |
| API Docs | `/docs` |
| Health   | `/health` |

#### Re-deploy After Changes
```bash
docker build -f Dockerfile.azure -t rtiassistantacr.azurecr.io/rti-assistant:latest .
docker push rtiassistantacr.azurecr.io/rti-assistant:latest
az webapp restart --resource-group rti-assistant-rg --name rti-assistant-app
```

#### Tear Down
```bash
az group delete --name rti-assistant-rg --yes --no-wait
```

### 8.4 Production Checklist
- [ ] Set production API keys in Azure App Settings
- [ ] Configure proper CORS origins in `app/config.py`
- [ ] Set up monitoring (health endpoint: `/health`)
- [ ] Configure rate limiting
- [ ] Set up backup for SQLite database
- [ ] Enable HTTPS (Azure provides SSL by default)
- [ ] Build RAG index inside container: `python scripts/build_rag_index.py`
- [ ] Seed database: `python scripts/seed_database.py`
- [ ] Use `requirements-azure.txt` for lean production image (excludes ML training deps)

---

## 9. Future Roadmap

### Phase 2 (v1.1)
- [ ] Email notifications for deadline reminders
- [ ] Bulk RTI filing for journalists
- [ ] Hindi language support

### Phase 3 (v1.2)
- [ ] Integration with RTI portal (rtionline.gov.in)
- [ ] Mobile app (React Native)
- [ ] Voice input for RTI queries

### Phase 4 (v2.0)
- [ ] Multi-tenant SaaS deployment
- [ ] Analytics dashboard for NGOs
- [ ] CIC order database integration

---

## 10. Success Metrics

| Metric | Target (6 months) |
|--------|-------------------|
| Monthly Active Users | 1,000 |
| RTI Drafts Generated | 5,000 |
| Appeals Filed (via app) | 500 |
| User Satisfaction (NPS) | > 50 |
| Classification Accuracy | > 85% |

---

## 11. Changelog

### v2.2.0 — April 2026 (Bug Fix Release)

| # | Area | Change |
|---|------|--------|
| 1 | **LLM / Groq** | Upgraded Groq model from decommissioned `llama-3.1-70b-versatile` to `llama-3.3-70b-versatile` across all 4 agents |
| 2 | **Draft Appeal Template** | Fixed `TemplateSyntaxError` (Jinja2 `{% endif %}` encountered before `{% endblock %}`) — page returned HTTP 500 on every request |
| 3 | **Know Your Rights** | Fixed `1 1 1` numbered list bug — `markdown_to_html()` was closing `<ol>` on empty lines between items; blank lines now skipped |
| 4 | **Response Classification** | Gibberish / very short text now returns `UNKNOWN` instead of silently defaulting to `NO_RESPONSE` |
| 5 | **Parse Response UI** | `UNKNOWN` result displays a red error alert — no analysis card, no "Go to Draft Appeal" link shown |
| 6 | **Session Guard** | `UNKNOWN` classification no longer written to Flask session — prevents stale gibberish data from reaching Draft Appeal |
| 7 | **Appeal Letter Content** | Removed `Note: This appeal must be filed within 30 days...` footer from the generated letter — it is UI-level metadata, not part of a formal legal document |

### v2.1.1 — Earlier April 2026
- Input validation and gibberish detection on RTI draft inputs
- Next Steps displayed as formatted numbered list
- `/api/top-filers` endpoint added
- Department auto-correction (keyword + TF-IDF)

---

## Appendix A: RTI Act Section Reference

| Section | Topic | Common Queries |
|---------|-------|----------------|
| 2 | Definitions | What is "information"? |
| 3 | Right to Information | Who can file RTI? |
| 4 | Proactive Disclosure | What must be published? |
| 6 | Request Filing | How to file RTI? |
| 7 | Response Disposal | Time limits |
| 8 | Exemptions | What can be denied? |
| 19 | Appeals | How to appeal? |
| 20 | Penalties | PIO penalties |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **RTI** | Right to Information Act, 2005 |
| **PIO** | Public Information Officer |
| **APIO** | Assistant Public Information Officer |
| **FAA** | First Appellate Authority |
| **CIC** | Central Information Commission |
| **SIC** | State Information Commission |
| **Deemed Refusal** | Automatic refusal if no response within 30 days |

---

*Document maintained by: RTI Assistant Development Team*  
*For questions: Refer to README.md or raise a GitHub issue*

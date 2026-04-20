# RTI Query Assistant & Document Tracker

> An AI-powered citizen-facing assistant for India's Right to Information Act, 2005.

**Version:** 2.2.0 | **Last Updated:** April 2026 | **Status:** Production-Ready | **Deployment:** Docker + Azure App Service

## Overview

The RTI Query Assistant is a production-ready application that helps Indian citizens draft legally
correct RTI applications from plain English, track response deadlines, parse and classify government
replies, answer rights questions using Retrieval-Augmented Generation (RAG) over the RTI Act 2005,
and auto-draft first appeal letters when applications are denied. It is built with FastAPI,
LangGraph, ChromaDB, Groq LLM, and a Flask + Bootstrap frontend.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  FLASK UI (mounted at /ui)                           │
│  Page 1: File RTI │ Page 2: Rights │ Page 3: Track │ Pages 4&5: ↓   │
│                   Parse Response   │   Draft Appeal                  │
│  Bootstrap 5 responsive templates                                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Internal API calls via requests
┌──────────────────────────▼──────────────────────────────────────────┐
│                    FASTAPI SERVER (port 8000)                        │
│  /api/draft-rti │ /api/check-rights │ /api/parse-response            │
│  /api/track/{id} │ /api/draft-appeal │ /api/departments               │
└──────────┬──────────────────────────────────────┬───────────────────┘
           │                                      │
┌──────────▼──────────┐              ┌────────────▼───────────────┐
│  LANGGRAPH           │              │  RAG PIPELINE               │
│  Orchestrator        │              │  ┌─────────────────────┐   │
│  ┌───────────────┐  │              │  │ ChromaDB             │   │
│  │ intent_clf    │  │              │  │ rti_act_chunks       │   │
│  │ draft_node    │  │              │  │ rti_case_chunks      │   │
│  │ rag_node      │◄─┼──────────────┤  └─────────────────────┘   │
│  │ response_node │  │              │  all-MiniLM-L6-v2           │
│  │ appeal_node   │  │              │  (local embeddings)          │
│  │ track_node    │  │              └────────────────────────────┘
│  └───────────────┘  │
└──────────┬──────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────┐
│  LLM LAYER                                                           │
│  PRIMARY: Groq llama-3.3-70b-versatile (free, fast)                 │
│  FALLBACK: OpenAI gpt-4o-mini (PDF OCR + Groq failure backup)       │
└──────────┬──────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────┐
│  DATABASE: SQLite (via SQLAlchemy)                                   │
│  Citizens │ Departments │ RTIApplications │ GovernmentResponses      │
│  Appeals  │ AuditLog                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- Python 3.11 or higher
- Two free API keys:
  - **OpenAI**: [platform.openai.com](https://platform.openai.com/api-keys)
  - **Groq**: [console.groq.com/keys](https://console.groq.com/keys)
- Docker Desktop (for containerised deployment)

---

## Quick Start (5 commands)

```bash
# 1. Clone and enter the project
cd rti-assistant

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 3. Add your API keys to .env (edit the file)
copy .env.example .env
# Open .env and fill in OPENAI_API_KEY and GROQ_API_KEY

# 4. Run the automated setup (installs packages, downloads data, builds index)
python setup.py

# 5. Start the API server (Flask UI is mounted at /ui)
uvicorn app.main:app --reload
```

Open **http://localhost:8000/ui/** for the UI and **http://localhost:8000/docs** for the API.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Health check — `{status, db_ready, chroma_ready}` |
| `POST` | `/api/draft-rti` | Generate RTI draft (with auto dept-correction) |
| `POST` | `/api/check-department` | Auto-detect correct department from query |
| `POST` | `/api/check-rights` | RTI rights Q&A via RAG |
| `POST` | `/api/parse-response` | Classify government response (PDF or text) |
| `GET`  | `/api/track/{id}` | Track single application — deadline, status, timeline |
| `GET`  | `/api/applications/{email}` | List all RTIs for a citizen (case-insensitive email) |
| `POST` | `/api/draft-appeal` | **Conditional** appeal generator — `no_appeal` for ALLOWED, `appeal_letter` otherwise |
| `GET`  | `/api/departments` | List all 13 seeded departments |
| `GET`  | `/api/top-filers?limit=N` | Top N citizens by application count |

---

## Dataset Sources

| Dataset | Source | Usage |
|---------|--------|-------|
| RTI Act 2005 PDF | `data/raw/rti_act_2005.pdf` | Primary RAG knowledge base, chunked by section |
| RTI Case Dataset | [jatinmehra/RTI-CASE-DATASET](https://huggingface.co/datasets/jatinmehra/RTI-CASE-DATASET) | RAG case precedents + DistilBERT training data |
| Synthetic Applications | Generated by Faker (en_IN) | 300 sample RTI applications for SQLite |

---

## How the 7 Capstone Components are Implemented

| Component | Implementation |
|-----------|---------------|
| **LLM Integration** | Groq `llama-3.3-70b-versatile` (primary), OpenAI `gpt-4o-mini` (fallback). All calls wrapped in try/except. |
| **RAG Pipeline** | ChromaDB with `all-MiniLM-L6-v2` embeddings. Two collections: RTI Act chunks (by section) + CIC case chunks (400-token overlap). |
| **LangGraph Agents** | StateGraph with intent classifier + 5 agent nodes (draft, rag, response, appeal, track). |
| **Fine-tuned Classifier** | DistilBERT trained on labeled RTI cases. Keyword fallback if model not found. |
| **FastAPI Backend** | 8 REST endpoints, CORS enabled, SQLAlchemy ORM, startup health checks. |
| **Flask Frontend** | 5-page UI mounted at /ui: draft, rights Q&A, tracking, response parsing, appeal drafting. Bootstrap 5 responsive templates. PDF download via reportlab. |
| **Evaluation Framework** | 6 automated evals: draft quality, RAG accuracy, classifier F1, deadline logic, E2E scenarios, ethics (hallucination + bias). |

---

## Evaluation Results (Targets)

| Component | Metric | Target | Status |
|-----------|--------|--------|--------|
| Draft Quality | Completeness Score | ≥ 0.83 | ✅ PASS |
| RAG Accuracy | Q&A Correct Rate | ≥ 0.70 | ✅ PASS |
| Classifier | Accuracy | ≥ 0.70 | ✅ PASS |
| Deadline Tracker | Unit Tests | 10/10 | ✅ PASS |
| End-to-End | Scenarios | ≥ 4/5 | ✅ PASS |
| Ethics | Hallucination < 5%, Disclaimer ≥ 90% | Both | ✅ PASS |

Run all evaluations:
```bash
python evaluation/run_all_evals.py
```

---

## Ethics & Safety

- **Hallucination Prevention**: All LLM outputs are validated with regex to ensure no RTI section
  number > 31 is cited (the RTI Act 2005 has only Sections 1–31).
- **AI Disclaimer Enforcement**: Every RTI draft includes the mandatory disclaimer
  *"Note: This is an AI-generated draft. Please review carefully before filing."*
  This is enforced both in the prompt template AND validated in evaluation.
- **Section Number Validation**: If a hallucinated section is detected, the agent regenerates
  the response with an explicit constraint prompt.
- **Bias Monitoring**: The ethics evaluation checks classifier accuracy across 4 department
  groups and flags disparities > 10%.

---

## Getting Your Free API Keys

| Service | URL | Free Tier |
|---------|-----|-----------|
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | $5 credit on signup |
| Groq | [console.groq.com/keys](https://console.groq.com/keys) | Free, no credit card needed |

---

## Docker Deployment

### Local Docker (Standard)

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -t rti-assistant:latest .
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/chroma_store:/app/chroma_store \
  -v $(pwd)/rti_tracker.db:/app/rti_tracker.db \
  rti-assistant:latest
```

| Service | URL |
|---------|-----|
| FastAPI + Flask UI | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Flask UI | http://localhost:8000/ui/ |
| Health Check | http://localhost:8000/health |

---

## Azure Deployment (App Service — Container)

Single container running FastAPI with Flask UI mounted at `/ui`, deployed to Azure App Service.

### Prerequisites
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- Docker Desktop running
- Azure subscription (free tier works)

### Step 1 — Login & Create Resources

```bash
# Login to Azure
az login

# Create resource group
az group create --name rti-assistant-rg --location eastus

# Create Azure Container Registry (ACR)
az acr create \
  --resource-group rti-assistant-rg \
  --name rtiassistantacr \
  --sku Basic \
  --admin-enabled true
```

### Step 2 — Build & Push Docker Image

```bash
# Build Azure-optimised image
docker build -f Dockerfile.azure -t rti-assistant:latest .

# Tag for ACR
docker tag rti-assistant:latest rtiassistantacr.azurecr.io/rti-assistant:latest

# Login to ACR
az acr login --name rtiassistantacr

# Push image
docker push rtiassistantacr.azurecr.io/rti-assistant:latest
```

### Step 3 — Create App Service Plan & Web App

```bash
# Create App Service plan (B1 = smallest paid tier, required for containers)
az appservice plan create \
  --name rti-assistant-plan \
  --resource-group rti-assistant-rg \
  --sku B1 \
  --is-linux

# Get ACR credentials
ACR_PASSWORD=$(az acr credential show \
  --name rtiassistantacr \
  --query "passwords[0].value" -o tsv)

# Create Web App with container
az webapp create \
  --resource-group rti-assistant-rg \
  --plan rti-assistant-plan \
  --name rti-assistant-app \
  --deployment-container-image-name rtiassistantacr.azurecr.io/rti-assistant:latest \
  --docker-registry-server-url https://rtiassistantacr.azurecr.io \
  --docker-registry-server-user rtiassistantacr \
  --docker-registry-server-password $ACR_PASSWORD
```

### Step 4 — Set Environment Variables

```bash
az webapp config appsettings set \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app \
  --settings \
    GROQ_API_KEY="your-groq-api-key" \
    OPENAI_API_KEY="your-openai-api-key" \
    SECRET_KEY="your-secret-key-here" \
    PYTHONPATH="/app" \
    WEBSITES_PORT=8000
```

### Step 5 — Enable Continuous Deployment (Optional)

```bash
# Enable CD from ACR
az webapp deployment container config \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app \
  --enable-cd true
```

### Step 6 — Verify Deployment

```bash
# Get the app URL
az webapp show \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app \
  --query defaultHostName -o tsv

# Check logs
az webapp log tail \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app
```

Your app will be live at: `https://rti-assistant-app.azurewebsites.net`

| Service | Azure URL |
|---------|----------|
| Flask UI | `https://rti-assistant-app.azurewebsites.net/ui/` |
| API Docs | `https://rti-assistant-app.azurewebsites.net/docs` |
| Health Check | `https://rti-assistant-app.azurewebsites.net/health` |

### Re-deploy After Code Changes

```bash
# Rebuild and push updated image
docker build -f Dockerfile.azure -t rtiassistantacr.azurecr.io/rti-assistant:latest .
docker push rtiassistantacr.azurecr.io/rti-assistant:latest

# Restart the web app to pull new image
az webapp restart \
  --resource-group rti-assistant-rg \
  --name rti-assistant-app
```

### Tear Down

```bash
# Delete everything (saves cost)
az group delete --name rti-assistant-rg --yes --no-wait
```

---

## Changelog

### v2.2.0 — April 2026

#### Bug Fixes
| # | Area | Fix |
|---|------|-----|
| 1 | **Groq LLM** | Upgraded model from decommissioned `llama-3.1-70b-versatile` to `llama-3.3-70b-versatile` across all agents |
| 2 | **Draft Appeal page** | Fixed `TemplateSyntaxError` — broken Jinja2 `{% if/elif/endif %}` block caused `500 Internal Server Error` on every GET request |
| 3 | **Know Your Rights** | Fixed numbered list showing `1 1 1` — `markdown_to_html()` was closing `<ol>` on blank lines between items; now blank lines are skipped during list parsing |
| 4 | **Response Classification** | Gibberish / too-short input no longer silently defaults to `NO_RESPONSE`; returns `UNKNOWN` classification and skips LLM call entirely |
| 5 | **Parse Response UI** | `UNKNOWN` classification displays a clear red error alert instead of a normal result card; no "Go to Draft Appeal" link is shown |
| 6 | **Flask Session** | Gibberish inputs (`UNKNOWN`) are no longer stored in session — prevents stale data from pre-filling the Draft Appeal form |
| 7 | **Appeal Letter** | Removed the `Note: This appeal must be filed within 30 days...` footer from the generated letter body (it is meta-information already shown in the UI, not part of a formal legal document) |

---

## Project Structure

```
rti-assistant/
├── app/                    # FastAPI application
│   ├── agents/             # LangGraph agents
│   ├── api/routes/         # API route handlers
│   ├── database/           # SQLAlchemy models, schemas, CRUD
│   ├── rag/                # ChromaDB indexer and retriever
│   └── utils/              # PDF parser, deadline tracker, prompt templates
├── data/                   # Datasets (raw, processed, synthetic)
├── evaluation/             # 6 evaluation scripts + golden Q&A pairs
├── frontend/               # Flask UI
│   ├── flask_app.py        # Flask application
│   └── templates/          # Jinja2 HTML templates
├── models/rti_classifier/  # Fine-tuned DistilBERT (after training)
├── scripts/                # Setup scripts (download, seed, index, finetune)
├── setup.py                # One-click setup runner
└── requirements.txt        # Runtime + setup dependencies (see requirements-azure.txt for lean Docker)
```

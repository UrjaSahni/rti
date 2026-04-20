"""
FastAPI main application entry point.

Configures:
- CORS middleware
- All API routers under /api prefix
- Startup event: creates DB tables, checks ChromaDB
- Health check endpoint
- Mounts Flask frontend at /ui
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.database.models import create_tables
from app.database.schemas import HealthResponse
from app.rag.indexer import check_index_exists
from app.api.routes import rti, rights, response, appeal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — runs startup tasks."""
    # Create database tables
    try:
        create_tables()
        print("[startup] Database tables created/verified.")
    except Exception as e:
        print(f"[startup] DB init warning: {e}")

    # Check ChromaDB index
    try:
        status = check_index_exists()
        if not status.get("act_ready"):
            print("[startup] WARNING: RTI Act chunks not indexed.")
            print("[startup] Run: python scripts/build_rag_index.py")
        if not status.get("cases_ready"):
            print("[startup] WARNING: CIC case chunks not indexed.")
            print("[startup] Run: python scripts/build_rag_index.py")
        if status.get("act_ready") and status.get("cases_ready"):
            print("[startup] ChromaDB collections ready.")
    except Exception as e:
        print(f"[startup] ChromaDB check failed: {e}")

    yield
    # Shutdown (nothing to clean up)


app = FastAPI(
    title="RTI Query Assistant API",
    description=(
        "AI-powered Right to Information assistant: draft RTI applications, "
        "know your rights, parse government responses, track deadlines, "
        "and draft first appeal letters."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───────────────────────────────────────────────────────────────────
app.include_router(rti.router, prefix="/api", tags=["RTI Applications"])
app.include_router(rights.router, prefix="/api", tags=["Rights Q&A"])
app.include_router(response.router, prefix="/api", tags=["Response Parsing"])
app.include_router(appeal.router, prefix="/api", tags=["Appeals"])


# ─── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    API health check endpoint.

    Verifies database connectivity and ChromaDB collection readiness.

    Returns:
        HealthResponse with status, chroma_ready, and db_ready flags.
    """
    db_ready = False
    try:
        from app.database.models import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ready = True
    except Exception:
        pass

    chroma_status = check_index_exists()
    chroma_ready = chroma_status.get("act_ready", False)

    return HealthResponse(
        status="ok",
        chroma_ready=chroma_ready,
        db_ready=db_ready,
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — redirect to Flask frontend."""
    return RedirectResponse(url="/ui/")


# ─── Mount Flask Frontend ──────────────────────────────────────────────────────
def mount_flask_app():
    """Mount Flask frontend at /ui."""
    try:
        from fastapi.middleware.wsgi import WSGIMiddleware
        from frontend.flask_app import app as flask_app
        
        # Update Flask's API_BASE to use relative path
        flask_app.config["API_BASE_URL"] = os.environ.get("API_BASE_URL", "http://localhost:8000/api")
        
        app.mount("/ui", WSGIMiddleware(flask_app))
        print("[startup] Flask frontend mounted at /ui")
    except ImportError as e:
        print(f"[startup] Flask frontend not available: {e}")

mount_flask_app()

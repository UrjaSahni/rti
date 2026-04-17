"""
RAG Indexer — builds ChromaDB vector collections from:
  1. DATASET/RTI-Act_English.pdf  (chunked by section heading)
  2. DATASET/cic_orders/*.txt  (chunked at 400 tokens with 50 token overlap)

Collections created:
  - rti_act_chunks   : RTI Act sections
  - rti_case_chunks  : CIC case orders
"""
import re
import os
from pathlib import Path
from typing import List, Dict

import chromadb
from sentence_transformers import SentenceTransformer
import pdfplumber

from app.config import settings as app_settings, BASE_DIR, DATA_RAW_DIR, CIC_ORDERS_DIR


# ─── Model (loaded once) ───────────────────────────────────────────────────────
_embed_model = None


def get_embed_model() -> SentenceTransformer:
    """
    Return (and lazily load) the sentence-transformer embedding model.

    Returns:
        SentenceTransformer instance for all-MiniLM-L6-v2.
    """
    global _embed_model
    if _embed_model is None:
        print("[indexer] Loading embedding model (all-MiniLM-L6-v2)...")
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


def get_chroma_client() -> chromadb.Client:
    """
    Return a persistent ChromaDB client at the configured chroma_path.

    Returns:
        chromadb.Client connected to the persistent store.
    """
    chroma_dir = BASE_DIR / app_settings.chroma_path.lstrip("./")
    chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_dir))


# ─── PDF chunking ──────────────────────────────────────────────────────────────

def _extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract full text from a PDF using pdfplumber.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Full text as a single string.
    """
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return "\n".join(pages)


def _chunk_by_section(text: str) -> List[Dict]:
    """
    Split RTI Act text into chunks by section heading.

    Detects patterns like "Section 1", "SECTION 2", "1.", or standalone
    numbered headings to split the document.

    Args:
        text: Full text of the RTI Act PDF.

    Returns:
        List of dicts: {"text": str, "section_number": str, "source": str}
    """
    # Split on "Section X" or "SECTION X" boundary lines
    section_pattern = re.compile(
        r"((?:^|\n)\s*(?:Section|SECTION)\s+(\d{1,2})\b[^\n]*)",
        re.IGNORECASE
    )

    chunks = []
    splits = section_pattern.split(text)

    # splits alternates: [preamble, full_match, group2, body, full_match, group2, body ...]
    if len(splits) < 3:
        # No section headings found — chunk by paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        for i, para in enumerate(paragraphs):
            chunks.append({
                "text": para,
                "section_number": f"para_{i}",
                "source": "rti_act_2005.pdf",
            })
        return chunks

    # Preamble (before first section)
    preamble = splits[0].strip()
    if len(preamble) > 50:
        chunks.append({
            "text": preamble,
            "section_number": "preamble",
            "source": "rti_act_2005.pdf",
        })

    # Process section triples: (heading_text, section_num_str, body)
    i = 1
    while i + 2 <= len(splits):
        heading = splits[i].strip()
        sec_num = splits[i + 1].strip()
        body = splits[i + 2].strip() if i + 2 < len(splits) else ""
        combined = f"{heading}\n{body}".strip()
        if combined:
            chunks.append({
                "text": combined,
                "section_number": sec_num,
                "source": "rti_act_2005.pdf",
            })
        i += 3

    return chunks


def _chunk_text_by_tokens(text: str, max_tokens: int = 400, overlap: int = 50) -> List[str]:
    """
    Split a long text into overlapping chunks by approximate token count.

    Uses whitespace-split words as a proxy for tokens.

    Args:
        text: The text to chunk.
        max_tokens: Maximum words per chunk.
        overlap: Number of words to overlap between consecutive chunks.

    Returns:
        List of text chunk strings.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start += max_tokens - overlap
    return chunks


# ─── Indexing functions ────────────────────────────────────────────────────────

def index_rti_act(client: chromadb.Client, model: SentenceTransformer) -> int:
    """
    Index the RTI Act 2005 PDF into the 'rti_act_chunks' ChromaDB collection.

    Args:
        client: ChromaDB persistent client.
        model: SentenceTransformer for generating embeddings.

    Returns:
        Number of chunks indexed.
    """
    # Use the shared DATASET folder at project parent level
    pdf_path = BASE_DIR.parent / "DATASET" / "RTI-Act_English.pdf"
    if not pdf_path.exists():
        print(f"[indexer] WARNING: RTI Act PDF not found at {pdf_path}")
        return 0

    print(f"[indexer] Reading RTI Act PDF: {pdf_path}")
    text = _extract_pdf_text(pdf_path)
    chunks = _chunk_by_section(text)
    print(f"[indexer] Indexing {len(chunks)} RTI Act chunks...")

    collection = client.get_or_create_collection(
        name="rti_act_chunks",
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 50
    stored = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c["text"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()
        ids = [f"act_{i + j}" for j in range(len(batch))]
        metadatas = [
            {
                "source": c["source"],
                "section_number": c["section_number"],
                "doc_type": "act",
            }
            for c in batch
        ]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        stored += len(batch)

    print(f"[indexer] Stored {stored} RTI Act chunks.")
    return stored


def index_cic_cases(client: chromadb.Client, model: SentenceTransformer) -> int:
    """
    Index CIC case order .txt files into the 'rti_case_chunks' ChromaDB collection.

    Args:
        client: ChromaDB persistent client.
        model: SentenceTransformer for generating embeddings.

    Returns:
        Number of chunks indexed.
    """
    if not CIC_ORDERS_DIR.exists():
        print(f"[indexer] WARNING: CIC orders directory not found: {CIC_ORDERS_DIR}")
        return 0

    txt_files = list(CIC_ORDERS_DIR.glob("*.txt"))
    if not txt_files:
        print("[indexer] WARNING: No .txt files found in cic_orders/")
        return 0

    print(f"[indexer] Found {len(txt_files)} CIC case files. Chunking...")

    collection = client.get_or_create_collection(
        name="rti_case_chunks",
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks = []
    all_metas = []

    for txt_file in txt_files:
        case_text = txt_file.read_text(encoding="utf-8", errors="ignore")
        sub_chunks = _chunk_text_by_tokens(case_text, max_tokens=400, overlap=50)
        for chunk in sub_chunks:
            if len(chunk.strip()) > 30:
                all_chunks.append(chunk.strip())
                all_metas.append({
                    "source": txt_file.name,
                    "section_number": "N/A",
                    "doc_type": "case",
                })

    print(f"[indexer] Indexing {len(all_chunks)} CIC case chunks...")

    batch_size = 50
    stored = 0
    for i in range(0, len(all_chunks), batch_size):
        batch_texts = all_chunks[i : i + batch_size]
        batch_metas = all_metas[i : i + batch_size]
        embeddings = model.encode(batch_texts, show_progress_bar=False).tolist()
        ids = [f"case_{i + j}" for j in range(len(batch_texts))]
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=batch_texts,
            metadatas=batch_metas,
        )
        stored += len(batch_texts)

    print(f"[indexer] Stored {stored} CIC case chunks.")
    return stored


def build_index() -> Dict[str, int]:
    """
    Build (or rebuild) both ChromaDB collections from scratch.

    Returns:
        Dict with keys 'act_chunks' and 'case_chunks' showing counts.
    """
    client = get_chroma_client()
    model = get_embed_model()

    act_count = index_rti_act(client, model)
    case_count = index_cic_cases(client, model)

    print(f"\nChromaDB ready: {act_count + case_count} total chunks indexed.")
    print(f"  - rti_act_chunks:  {act_count} chunks")
    print(f"  - rti_case_chunks: {case_count} chunks")
    return {"act_chunks": act_count, "case_chunks": case_count}


def check_index_exists() -> Dict[str, bool]:
    """
    Check whether the ChromaDB collections contain data.

    Returns:
        Dict with keys 'act_ready' and 'cases_ready'.
    """
    try:
        client = get_chroma_client()
        result = {"act_ready": False, "cases_ready": False}
        col_names = [c.name for c in client.list_collections()]
        if "rti_act_chunks" in col_names:
            col = client.get_collection("rti_act_chunks")
            result["act_ready"] = col.count() > 0
        if "rti_case_chunks" in col_names:
            col = client.get_collection("rti_case_chunks")
            result["cases_ready"] = col.count() > 0
        return result
    except Exception:
        return {"act_ready": False, "cases_ready": False}


if __name__ == "__main__":
    build_index()

"""
RAG Retriever — queries ChromaDB collections and returns context
for LLM prompts.

Collections:
  - rti_act_chunks   (doc_type="act")
  - rti_case_chunks  (doc_type="case")
"""
import re
from typing import Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import settings as app_settings, BASE_DIR
from app.rag.indexer import get_chroma_client, get_embed_model


def retrieve_rti_context(
    query: str,
    doc_type: Optional[str] = None,
    top_k: int = 5,
) -> Dict:
    """
    Retrieve relevant RTI Act / CIC case chunks from ChromaDB.

    Queries one or both collections depending on doc_type and merges results.

    Args:
        query: User's question or search text.
        doc_type: "act" — query only rti_act_chunks;
                  "case" — query only rti_case_chunks;
                  None — query both and merge.
        top_k: Number of top results to retrieve per collection.

    Returns:
        Dict with keys:
            "answer_context" (str): Combined text context for the LLM prompt.
            "sources"        (list[str]): Source file names.
            "sections_cited" (list[str]): Distinct section numbers referenced.
    """
    client = get_chroma_client()
    model = get_embed_model()

    query_embedding = model.encode([query], show_progress_bar=False).tolist()[0]

    docs: List[str] = []
    sources: List[str] = []
    sections: List[str] = []

    collections_to_query = []
    if doc_type == "act":
        collections_to_query = ["rti_act_chunks"]
    elif doc_type == "case":
        collections_to_query = ["rti_case_chunks"]
    else:
        collections_to_query = ["rti_act_chunks", "rti_case_chunks"]

    existing_collections = {c.name for c in client.list_collections()}  # works in chromadb 1.x

    for col_name in collections_to_query:
        if col_name not in existing_collections:
            print(
                f"[retriever] Collection '{col_name}' not found. "
                "Run: python scripts/build_rag_index.py"
            )
            continue

        collection = client.get_collection(col_name)

        if collection.count() == 0:
            print(
                f"[retriever] Collection '{col_name}' is empty. "
                "Run: python scripts/build_rag_index.py"
            )
            continue

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        for doc, meta in zip(
            results["documents"][0], results["metadatas"][0]
        ):
            docs.append(doc)
            sources.append(meta.get("source", "unknown"))
            sec = meta.get("section_number", "")
            if sec and sec not in ("N/A", "preamble") and sec not in sections:
                sections.append(sec)

    # Build combined context string
    answer_context = "\n\n---\n\n".join(docs) if docs else "No relevant context found."

    return {
        "answer_context": answer_context,
        "sources": list(set(sources)),
        "sections_cited": sections,
    }


def validate_section_numbers(text: str) -> List[int]:
    """
    Extract all RTI section numbers mentioned in the given text.

    Args:
        text: LLM-generated answer text.

    Returns:
        List of integer section numbers found in the text.
    """
    matches = re.findall(r"[Ss]ection\s+(\d+)", text)
    return [int(m) for m in matches]


def has_hallucinated_sections(text: str, max_valid: int = 31) -> bool:
    """
    Check whether the text cites any section number outside the valid range.

    The RTI Act 2005 has only Sections 1–31.

    Args:
        text: LLM-generated text to validate.
        max_valid: Maximum valid section number (31 for RTI Act).

    Returns:
        True if any section number > max_valid is found.
    """
    section_nums = validate_section_numbers(text)
    return any(n > max_valid for n in section_nums)

"""
RAG Agent — answers "what are my RTI rights?" questions using
ChromaDB-backed context from the RTI Act 2005 and CIC case precedents.

Enhanced with:
- Rule-based answers for critical RTI queries
- Section mapping and query expansion
- Fuzzy matching fallback
- Never returns "not covered" for valid RTI topics

Uses Groq (llama-3.3-70b-versatile) primary, OpenAI (gpt-4o-mini) fallback.
Validates that no section number > 31 is cited.
"""
import re
from typing import Dict, List

from groq import Groq
from openai import OpenAI

from app.config import settings
from app.utils.prompt_templates import RIGHTS_QA_PROMPT
from app.rag.retriever import retrieve_rti_context, has_hallucinated_sections
from app.utils.rti_knowledge_base import (
    check_rule_based_answer,
    find_matching_sections,
    build_enhanced_context,
    get_section_context,
    RTI_SECTION_MAP,
)


def _call_groq(prompt: str) -> str:
    """
    Call Groq API (llama-3.3-70b-versatile).

    Args:
        prompt: Fully-formatted prompt string.

    Returns:
        LLM response text.
    """
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    """
    Call OpenAI API (gpt-4o-mini) as fallback.

    Args:
        prompt: Fully-formatted prompt string.

    Returns:
        LLM response text.
    """
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1024,
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
        print(f"[rag_agent] Groq failed ({groq_err}). Falling back to OpenAI...")
        try:
            return _call_openai(prompt)
        except Exception as oai_err:
            raise RuntimeError(
                f"Both LLMs failed. Groq: {groq_err} | OpenAI: {oai_err}"
            )


def _extract_sections(text: str) -> List[str]:
    """
    Extract all RTI section references from a text string.

    Args:
        text: The LLM answer text.

    Returns:
        Sorted list of unique section numbers as strings.
    """
    matches = re.findall(r"[Ss]ection\s+(\d+)", text)
    return sorted(set(matches), key=lambda x: int(x))


def _estimate_confidence(answer: str, context: str, question: str) -> float:
    """
    Estimate answer confidence based on section citation and context overlap.

    Args:
        answer: The LLM-generated answer.
        context: The retrieved RAG context.
        question: The original user question.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    score = 0.5
    if "Section" in answer:
        score += 0.2
    if "not covered in the provided RTI Act sections" in answer:
        score = 0.3
    # Check keyword overlap between question and context
    q_words = set(question.lower().split())
    ctx_words = set(context.lower().split())
    overlap = len(q_words & ctx_words) / max(len(q_words), 1)
    score += min(overlap * 0.3, 0.3)
    return min(round(score, 2), 1.0)


def run_rag_agent(question: str) -> Dict:
    """
    Answer an RTI rights question using a multi-layer approach:
    
    Layer 1: Rule-based answers (highest confidence for critical queries)
    Layer 2: Knowledge base section mapping with query expansion
    Layer 3: RAG + LLM with enhanced context
    Layer 4: Fallback with fuzzy matching (never says "not covered" for valid RTI topics)

    Args:
        question: The citizen's rights question in plain English.

    Returns:
        Dict with keys: answer, source_sections, case_precedents, confidence.
    """
    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 1: Rule-based answers for critical RTI queries
    # ═══════════════════════════════════════════════════════════════════════════
    rule_answer = check_rule_based_answer(question)
    if rule_answer and rule_answer.get("answer"):
        print(f"[rag_agent] Rule-based answer triggered: {rule_answer.get('source', 'unknown')}")
        return {
            "answer": rule_answer["answer"] + f"\n\nReference: Section {rule_answer['section']} of the Right to Information Act, 2005",
            "source_sections": [rule_answer["section"]],
            "case_precedents": [],
            "confidence": rule_answer["confidence"],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 2: Section mapping with query expansion
    # ═══════════════════════════════════════════════════════════════════════════
    matching_sections = find_matching_sections(question)
    
    # If we have a high-confidence section match, build targeted context
    section_hints = []
    if matching_sections:
        for section_num, score in matching_sections[:3]:
            if score >= 0.4:
                section_hints.append(section_num)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 3: RAG retrieval with enhanced context
    # ═══════════════════════════════════════════════════════════════════════════
    # Step 1: Retrieve RTI Act context
    act_context = retrieve_rti_context(question, doc_type="act")

    # Step 2: Retrieve CIC case precedents
    case_context = retrieve_rti_context(question, doc_type="case")

    # Combine and enhance contexts
    combined_context = act_context["answer_context"]
    
    # Enhance with knowledge base sections if RAG context is thin
    combined_context = build_enhanced_context(question, combined_context)
    
    # Add section hints if available
    if section_hints and "No relevant context found" not in combined_context:
        hint_text = "\n\n=== RELEVANT SECTIONS TO CONSIDER ===\n"
        for sec in section_hints:
            hint_text += get_section_context(sec) + "\n"
        combined_context += hint_text
    
    if case_context["answer_context"] != "No relevant context found.":
        combined_context += "\n\n=== RELEVANT CIC CASE PRECEDENTS ===\n\n"
        combined_context += case_context["answer_context"]

    # Step 3: Build prompt and call LLM
    prompt = RIGHTS_QA_PROMPT.format(
        question=question,
        context=combined_context,
    )

    answer = _call_llm(prompt)

    # ═══════════════════════════════════════════════════════════════════════════
    # LAYER 4: Fallback — prevent false "not covered" responses
    # ═══════════════════════════════════════════════════════════════════════════
    if "not covered in the provided RTI Act sections" in answer.lower() or \
       "not covered in the rti act" in answer.lower():
        print("[rag_agent] LLM returned 'not covered'. Attempting fallback...")
        
        # Try with explicit section context from knowledge base
        if matching_sections:
            best_section = matching_sections[0][0]
            section_data = RTI_SECTION_MAP.get(best_section, {})
            
            if section_data:
                fallback_context = f"""
IMPORTANT: The query IS covered by the RTI Act. Use this information:

Section {best_section}: {section_data.get('title', '')}
{section_data.get('summary', '')}

Keywords related to this section: {', '.join(section_data.get('keywords', []))}
"""
                fallback_prompt = f"""
You are an RTI legal expert. The user asked: {question}

This question IS covered by the RTI Act 2005. Use this context:
{fallback_context}

{combined_context}

Provide a clear, helpful answer. DO NOT say "not covered" — this topic IS addressed in the RTI Act.
End with: "Reference: Section [X] of the Right to Information Act, 2005"
"""
                try:
                    answer = _call_llm(fallback_prompt)
                except Exception as e:
                    print(f"[rag_agent] Fallback LLM call failed: {e}")
                    # Use knowledge base summary as last resort
                    answer = f"{section_data.get('summary', 'Please refer to the RTI Act.')}\n\nReference: Section {best_section} of the Right to Information Act, 2005"

    # Step 5: Validate section numbers — no hallucinations beyond Section 31
    if has_hallucinated_sections(answer):
        print("[rag_agent] Hallucinated section detected. Regenerating with explicit constraint...")
        strict_prompt = (
            prompt
            + "\n\nCRITICAL REMINDER: The RTI Act 2005 has ONLY Sections 1 through 31. "
            "Do NOT cite any section number above 31 under any circumstances."
        )
        try:
            answer = _call_llm(strict_prompt)
        except Exception as e:
            print(f"[rag_agent] Regeneration failed: {e}. Using original answer.")

    # Extract cited sections
    source_sections = _extract_sections(answer)
    
    # Add matched sections if not already cited
    if section_hints:
        for sec in section_hints:
            if sec not in source_sections:
                source_sections.append(sec)

    # Build case precedent summaries (first 200 chars of each case chunk)
    case_precedents: List[str] = []
    if case_context["answer_context"] != "No relevant context found.":
        for chunk in case_context["answer_context"].split("\n\n---\n\n"):
            preview = chunk.strip()[:200]
            if preview:
                case_precedents.append(preview)

    confidence = _estimate_confidence(answer, combined_context, question)
    
    # Boost confidence if we had section matches
    if matching_sections and matching_sections[0][1] >= 0.5:
        confidence = max(confidence, 0.85)

    return {
        "answer": answer,
        "source_sections": source_sections,
        "case_precedents": case_precedents[:3],  # top 3 precedents
        "confidence": confidence,
    }

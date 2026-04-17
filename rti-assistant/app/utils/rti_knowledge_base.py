"""
RTI Knowledge Base — Section mappings, query expansion, and rule-based overrides.

This module provides:
1. Comprehensive mapping of RTI concepts to sections
2. Semantic query expansion using keywords
3. Rule-based overrides for critical queries
4. Fuzzy matching for query understanding
"""
import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: RTI ACT SECTION MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

RTI_SECTION_MAP: Dict[str, Dict] = {
    # Section 2 - Definitions
    "2": {
        "title": "Definitions",
        "keywords": ["definition", "meaning", "what is", "who is", "public authority", "information", "record", "right to information"],
        "summary": "Defines key terms including 'information', 'public authority', 'record', 'right to information', etc."
    },
    
    # Section 3 - Right to Information
    "3": {
        "title": "Right to Information",
        "keywords": ["right to information", "fundamental right", "citizen right", "access to information"],
        "summary": "All citizens have the right to information subject to the provisions of this Act."
    },
    
    # Section 4 - Obligations of Public Authorities
    "4": {
        "title": "Obligations of Public Authorities",
        "keywords": ["suo motu", "proactive disclosure", "publish", "public authority obligation", "maintain records", "website"],
        "summary": "Public authorities must maintain records and publish information proactively within 120 days."
    },
    
    # Section 5 - Designation of PIOs
    "5": {
        "title": "Designation of Public Information Officers",
        "keywords": ["pio", "public information officer", "designation", "assistant pio", "apio", "cpio"],
        "summary": "Every public authority must designate PIOs and APIOs within 100 days."
    },
    
    # Section 6 - Request for Information
    "6": {
        "title": "Request for Obtaining Information",
        "keywords": ["application", "request", "how to file", "filing", "submit rti", "form"],
        "summary": "A person can make a request in writing or electronic means in English, Hindi, or official language."
    },
    "6(1)": {
        "title": "Making RTI Request",
        "keywords": ["submit request", "file rti", "make application", "request information"],
        "summary": "Request shall be made in writing or through electronic means, accompanied by prescribed fee."
    },
    "6(3)": {
        "title": "Transfer of Application",
        "keywords": ["transfer", "forward", "wrong department", "not held", "another authority", "redirect"],
        "summary": "If information is held by another public authority, the application shall be transferred within 5 days."
    },
    
    # Section 7 - Disposal of Request
    "7": {
        "title": "Disposal of Request",
        "keywords": ["response", "disposal", "provide information", "time limit", "reply"],
        "summary": "PIO shall provide information within 30 days or give reasons for rejection."
    },
    "7(1)": {
        "title": "PIO Response Time",
        "keywords": ["30 days", "response time", "pio deadline", "time limit", "reply period", "when will i get response", "how long"],
        "summary": "PIO must respond within 30 days from receipt of request. Extendable by 30 more days with written reasons."
    },
    "7(2)": {
        "title": "Deemed Refusal",
        "keywords": ["deemed refusal", "no response", "failure to respond", "deemed denied", "automatic refusal", "no reply"],
        "summary": "If PIO fails to give decision within 30 days, it is deemed refusal and citizen can appeal."
    },
    "7(5)": {
        "title": "BPL Fee Exemption",
        "keywords": ["bpl", "below poverty line", "fee exemption", "free", "no fee", "poor", "waiver"],
        "summary": "No fee shall be charged from persons who are below the poverty line."
    },
    "7(6)": {
        "title": "Life or Liberty - 48 Hours",
        "keywords": ["life", "liberty", "48 hours", "urgent", "emergency", "life or liberty"],
        "summary": "Information concerning life or liberty of a person shall be provided within 48 hours."
    },
    
    # Section 8 - Exemption from Disclosure
    "8": {
        "title": "Exemption from Disclosure",
        "keywords": ["exemption", "exempt", "cannot disclose", "not allowed", "restriction", "prohibited"],
        "summary": "Certain categories of information are exempt from disclosure."
    },
    "8(1)": {
        "title": "Exempted Information Categories",
        "keywords": ["national security", "sovereignty", "cabinet papers", "trade secrets", "privacy", "fiduciary"],
        "summary": "Lists 10 categories of exempt information including security, privacy, trade secrets, etc."
    },
    "8(1)(j)": {
        "title": "Personal Information Exemption",
        "keywords": ["personal information", "privacy", "personal data", "third party", "invasion of privacy"],
        "summary": "Personal information which has no relationship to public activity or public interest is exempt."
    },
    
    # Section 9 - Grounds for Rejection
    "9": {
        "title": "Grounds for Rejection",
        "keywords": ["rejection", "reject", "refuse", "infringement", "copyright", "intellectual property"],
        "summary": "Request can be rejected if disclosure would infringe copyright of any person other than the State."
    },
    
    # Section 10 - Severability
    "10": {
        "title": "Severability",
        "keywords": ["partial disclosure", "severable", "part of record", "redact", "separate"],
        "summary": "If part of information is exempt, the remaining part shall be provided after severing the exempt portion."
    },
    
    # Section 11 - Third Party Information
    "11": {
        "title": "Third Party Information",
        "keywords": ["third party", "confidential", "trade secret", "notice", "objection"],
        "summary": "Third party must be given notice and opportunity to make representations before disclosing their information."
    },
    
    # Section 19 - Appeal
    "19": {
        "title": "Appeal",
        "keywords": ["appeal", "complaint", "grievance", "challenge", "review"],
        "summary": "Any person who does not receive a decision or is aggrieved may prefer an appeal."
    },
    "19(1)": {
        "title": "First Appeal",
        "keywords": ["first appeal", "faa", "appellate authority", "30 days appeal", "appeal to officer senior"],
        "summary": "First appeal to officer senior in rank to PIO within 30 days from expiry of prescribed period or receipt of decision."
    },
    "19(3)": {
        "title": "Second Appeal",
        "keywords": ["second appeal", "cic", "information commission", "90 days", "central information commission", "state information commission"],
        "summary": "Second appeal to Central/State Information Commission within 90 days from the date of decision of first appeal."
    },
    "19(4)": {
        "title": "Appeal to Commission (Third Party)",
        "keywords": ["third party appeal", "disclosure objection"],
        "summary": "Third party can appeal to Commission against order permitting disclosure."
    },
    "19(5)": {
        "title": "Burden of Proof",
        "keywords": ["burden of proof", "onus", "prove", "justify denial"],
        "summary": "Onus of proving that denial was justified is on the PIO."
    },
    "19(7)": {
        "title": "Appeal Decision Time",
        "keywords": ["appeal decision", "dispose appeal", "appeal timeline"],
        "summary": "Appeal should be disposed of within 30 days, extendable to 45 days with reasons in writing."
    },
    "19(8)": {
        "title": "Commission Powers",
        "keywords": ["commission powers", "cic powers", "direction", "order"],
        "summary": "Commission can require public authority to provide information, impose penalty, award compensation."
    },
    
    # Section 20 - Penalties
    "20": {
        "title": "Penalties",
        "keywords": ["penalty", "fine", "punishment", "rs 250", "per day", "disciplinary action", "malafide"],
        "summary": "Penalty of Rs. 250 per day up to Rs. 25,000 for delay or malafide denial. Disciplinary action for persistent defaults."
    },
    "20(1)": {
        "title": "Penalty Amount",
        "keywords": ["penalty amount", "how much fine", "250 per day", "25000 maximum"],
        "summary": "Penalty of Rs. 250 per day, maximum Rs. 25,000, for failure to provide information without reasonable cause."
    },
    
    # Section 22 - Overriding Effect
    "22": {
        "title": "Act to Have Overriding Effect",
        "keywords": ["override", "official secrets", "prevail", "notwithstanding"],
        "summary": "RTI Act overrides Official Secrets Act 1923 and other inconsistent laws."
    },
    
    # Section 24 - Excluded Organizations
    "24": {
        "title": "Act Not to Apply to Certain Organizations",
        "keywords": ["excluded", "intelligence", "security agencies", "ib", "raw", "not applicable"],
        "summary": "Act does not apply to intelligence and security organizations specified in Second Schedule."
    },
    
    # Section 27 - Competent Authorities
    "27": {
        "title": "Power to Make Rules",
        "keywords": ["rules", "rule making", "competent authority"],
        "summary": "Appropriate Government may make rules to carry out provisions of this Act."
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: QUERY EXPANSION MAPPINGS
# ══════════════════════════════════════════════════════════════════════════════

QUERY_EXPANSIONS: Dict[str, List[str]] = {
    # Time-related expansions
    "time limit": ["deadline", "days", "period", "within", "how long", "when"],
    "deadline": ["time limit", "days", "within", "period", "last date"],
    "how long": ["time limit", "days", "deadline", "period"],
    
    # Appeal-related expansions
    "first appeal": ["19(1)", "appellate authority", "faa", "30 days appeal"],
    "second appeal": ["19(3)", "information commission", "cic", "sic", "90 days"],
    "appeal": ["first appeal", "second appeal", "grievance", "challenge", "review"],
    
    # Response-related expansions
    "no response": ["deemed refusal", "7(2)", "failure to respond", "no reply"],
    "deemed refusal": ["no response", "7(2)", "automatic refusal", "failure to respond"],
    
    # Fee-related expansions
    "fee": ["charges", "cost", "payment", "rs 10", "postal order"],
    "bpl": ["below poverty line", "fee exemption", "7(5)", "free", "poor"],
    "free": ["bpl", "fee exemption", "no charge"],
    
    # Exemption-related expansions
    "exempt": ["exemption", "section 8", "cannot disclose", "not allowed"],
    "personal information": ["8(1)(j)", "privacy", "third party"],
    
    # Time-critical expansions
    "urgent": ["life or liberty", "48 hours", "7(6)", "emergency"],
    "life or liberty": ["48 hours", "7(6)", "urgent", "emergency"],
    
    # PIO-related expansions
    "pio": ["public information officer", "cpio", "apio"],
    "response time": ["30 days", "7(1)", "pio deadline"],
    
    # Transfer-related expansions
    "transfer": ["6(3)", "forward", "redirect", "another department"],
    
    # Penalty-related expansions
    "penalty": ["fine", "punishment", "section 20", "rs 250", "disciplinary"],
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: RULE-BASED OVERRIDES (CRITICAL RTI FACTS)
# ══════════════════════════════════════════════════════════════════════════════

RULE_BASED_ANSWERS: Dict[str, Dict] = {
    "second_appeal_time": {
        "triggers": ["second appeal", "time limit second appeal", "second appeal deadline", 
                     "appeal to commission", "cic appeal", "sic appeal", "second appeal period",
                     "90 days", "appeal to information commission"],
        "answer": "The time limit for filing a Second Appeal to the Central/State Information Commission is 90 days from the date on which the decision of the First Appellate Authority was received or should have been received.",
        "section": "19(3)",
        "confidence": 0.98
    },
    "first_appeal_time": {
        "triggers": ["first appeal", "time limit first appeal", "first appeal deadline",
                     "appeal to faa", "appellate authority appeal", "30 days appeal"],
        "answer": "The time limit for filing a First Appeal to the First Appellate Authority (FAA) is 30 days from the expiry of the prescribed period (30 days) or from the receipt of the PIO's decision. This period can be extended if the FAA is satisfied that the appellant had sufficient cause for delay.",
        "section": "19(1)",
        "confidence": 0.98
    },
    "pio_response_time": {
        "triggers": ["pio response time", "pio deadline", "response deadline", "when will i get response",
                     "how long does pio have", "30 days response", "pio reply time"],
        "answer": "The PIO must provide information within 30 days from the date of receipt of the request. If information is sought concerns the life or liberty of a person, it shall be provided within 48 hours. The 30-day period can be extended by another 30 days if more time is needed, but the PIO must inform the applicant in writing with reasons.",
        "section": "7(1)",
        "confidence": 0.98
    },
    "deemed_refusal": {
        "triggers": ["deemed refusal", "no response", "pio did not respond", "no reply from pio",
                     "failure to respond", "what if no response", "pio silent"],
        "answer": "If the PIO fails to give a decision within 30 days, it is treated as a 'deemed refusal'. The applicant can directly file a First Appeal as if the request was refused. This is covered under Section 7(2) of the RTI Act.",
        "section": "7(2)",
        "confidence": 0.98
    },
    "life_liberty": {
        "triggers": ["life or liberty", "48 hours", "urgent information", "emergency rti",
                     "life threatening", "liberty at stake"],
        "answer": "If the information sought concerns the life or liberty of a person, the PIO must provide the information within 48 hours of receipt of the request. This is a special provision for urgent matters under Section 7(6).",
        "section": "7(6)",
        "confidence": 0.98
    },
    "bpl_fee": {
        "triggers": ["bpl fee", "below poverty line fee", "fee exemption bpl", "poor fee",
                     "no fee bpl", "free for bpl", "bpl card rti"],
        "answer": "Persons belonging to Below Poverty Line (BPL) category are exempt from paying any fee for RTI applications. They need to provide proof of their BPL status (BPL card/certificate) along with the application.",
        "section": "7(5)",
        "confidence": 0.98
    },
    "transfer_application": {
        "triggers": ["transfer application", "wrong department", "forward application",
                     "redirect rti", "information held elsewhere", "6(3)"],
        "answer": "If the information requested is held by or relates to another public authority, the PIO must transfer the application to that authority within 5 days and inform the applicant. The 30-day response period then starts from the date of transfer.",
        "section": "6(3)",
        "confidence": 0.98
    },
    "penalty_pio": {
        "triggers": ["penalty pio", "fine for pio", "punishment pio", "pio penalty amount",
                     "how much fine", "section 20 penalty", "disciplinary action pio"],
        "answer": "If a PIO fails to provide information within the specified time without reasonable cause, the Information Commission can impose a penalty of Rs. 250 per day until the information is provided, subject to a maximum of Rs. 25,000. The Commission can also recommend disciplinary action against the PIO for persistent failure or malafide denial.",
        "section": "20(1)",
        "confidence": 0.98
    },
    "exempted_information": {
        "triggers": ["what is exempt", "exempted information", "what cannot be disclosed",
                     "section 8 exemption", "rti exemptions"],
        "answer": "Section 8(1) lists 10 categories of information exempt from disclosure: (a) information affecting sovereignty, security, strategic interests; (b) information prohibited by court/tribunal; (c) breach of parliamentary privilege; (d) commercial confidence/trade secrets; (e) fiduciary relationships; (f) foreign government information; (g) endangering life/safety; (h) impeding investigation; (i) cabinet papers; (j) personal information with no public interest.",
        "section": "8(1)",
        "confidence": 0.98
    },
    "application_fee": {
        "triggers": ["application fee", "rti fee", "how much fee", "filing fee",
                     "fee for rti", "cost of rti", "rs 10"],
        "answer": "The application fee for RTI is Rs. 10 for Central Government departments. The fee can be paid through Indian Postal Order, Demand Draft, Banker's Cheque, or cash. State Governments may prescribe their own fee structure. BPL applicants are exempt from paying any fee.",
        "section": "6(1)",
        "confidence": 0.95
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def normalize_query(query: str) -> str:
    """Normalize a query for matching: lowercase, remove punctuation, collapse whitespace."""
    query = query.lower().strip()
    query = re.sub(r'[^\w\s]', ' ', query)
    query = re.sub(r'\s+', ' ', query)
    return query


def fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
    """Check if query fuzzy-matches target above threshold."""
    ratio = SequenceMatcher(None, normalize_query(query), normalize_query(target)).ratio()
    return ratio >= threshold


def extract_keywords(query: str) -> List[str]:
    """Extract meaningful keywords from a query."""
    stopwords = {'what', 'is', 'the', 'a', 'an', 'for', 'to', 'of', 'in', 'and', 'or', 
                 'how', 'can', 'i', 'do', 'does', 'my', 'under', 'about', 'tell', 'me',
                 'please', 'explain', 'describe', 'give', 'provide'}
    words = normalize_query(query).split()
    return [w for w in words if w not in stopwords and len(w) > 2]


def expand_query(query: str) -> List[str]:
    """Expand a query with related terms."""
    normalized = normalize_query(query)
    expansions = [normalized]
    
    for term, related in QUERY_EXPANSIONS.items():
        if term in normalized:
            expansions.extend(related)
    
    return list(set(expansions))


def find_matching_sections(query: str) -> List[Tuple[str, float]]:
    """
    Find RTI sections that match the query.
    
    Returns list of (section_number, confidence_score) tuples sorted by score.
    """
    normalized = normalize_query(query)
    keywords = extract_keywords(query)
    expanded = expand_query(query)
    
    matches: List[Tuple[str, float]] = []
    
    for section_num, section_data in RTI_SECTION_MAP.items():
        score = 0.0
        
        # Check title match
        if fuzzy_match(normalized, section_data["title"], 0.5):
            score += 0.3
        
        # Check keyword matches
        section_keywords = section_data.get("keywords", [])
        for kw in section_keywords:
            if kw in normalized:
                score += 0.25
            elif any(kw in exp for exp in expanded):
                score += 0.15
            elif any(fuzzy_match(q_kw, kw, 0.7) for q_kw in keywords):
                score += 0.1
        
        # Check summary match
        summary = section_data.get("summary", "").lower()
        for q_kw in keywords:
            if q_kw in summary:
                score += 0.1
        
        if score > 0.2:
            matches.append((section_num, min(score, 1.0)))
    
    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:5]  # Top 5 matches


def check_rule_based_answer(query: str) -> Optional[Dict]:
    """
    Check if query matches any rule-based answer.
    
    Returns the pre-defined answer dict if matched, else None.
    """
    normalized = normalize_query(query)
    keywords = extract_keywords(query)
    keyword_set = set(keywords)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 1: Explicit keyword combination checks (most specific first)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Second appeal detection (must have "second" explicitly)
    if "second" in normalized and "appeal" in normalized:
        return RULE_BASED_ANSWERS["second_appeal_time"] | {"source": "rule:second_appeal_time"}
    
    # First appeal detection (must have "first" explicitly, not second)
    if "first" in normalized and "appeal" in normalized and "second" not in normalized:
        return RULE_BASED_ANSWERS["first_appeal_time"] | {"source": "rule:first_appeal_time"}
    
    # 90 days strongly suggests second appeal
    if "90" in normalized and "appeal" in keyword_set:
        return RULE_BASED_ANSWERS["second_appeal_time"] | {"source": "rule:second_appeal_time"}
    
    # 30 days + appeal suggests first appeal
    if "30" in normalized and "appeal" in normalized and "second" not in normalized:
        return RULE_BASED_ANSWERS["first_appeal_time"] | {"source": "rule:first_appeal_time"}
    
    # Life/liberty detection
    if ("life" in keyword_set or "liberty" in keyword_set):
        return RULE_BASED_ANSWERS["life_liberty"] | {"source": "rule:life_liberty"}
    if "48 hours" in normalized or "48 hour" in normalized:
        return RULE_BASED_ANSWERS["life_liberty"] | {"source": "rule:life_liberty"}
    
    # Deemed refusal detection
    if "deemed" in normalized:
        return RULE_BASED_ANSWERS["deemed_refusal"] | {"source": "rule:deemed_refusal"}
    if "no response" in normalized or "no reply" in normalized:
        return RULE_BASED_ANSWERS["deemed_refusal"] | {"source": "rule:deemed_refusal"}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 2: Direct substring matches for other rules
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Skip appeal-related rules (already handled above)
    skip_rules = {"second_appeal_time", "first_appeal_time", "life_liberty", "deemed_refusal"}
    
    for rule_name, rule_data in RULE_BASED_ANSWERS.items():
        if rule_name in skip_rules:
            continue
            
        for trigger in rule_data["triggers"]:
            # Direct substring match
            if trigger in normalized:
                return {
                    "answer": rule_data["answer"],
                    "section": rule_data["section"],
                    "confidence": rule_data["confidence"],
                    "source": f"rule:{rule_name}"
                }
            
            # Fuzzy match for longer triggers
            if len(trigger.split()) >= 2 and fuzzy_match(normalized, trigger, 0.75):
                return {
                    "answer": rule_data["answer"],
                    "section": rule_data["section"],
                    "confidence": rule_data["confidence"],
                    "source": f"rule:{rule_name}"
                }
    
    return None


def get_section_context(section_num: str) -> str:
    """Get context text for a specific section."""
    section_data = RTI_SECTION_MAP.get(section_num, {})
    if section_data:
        return f"Section {section_num}: {section_data.get('title', 'Unknown')} - {section_data.get('summary', '')}"
    return ""


def build_enhanced_context(query: str, rag_context: str) -> str:
    """
    Enhance RAG context with section mapping information.
    
    If RAG context is thin, inject relevant section summaries.
    """
    matching_sections = find_matching_sections(query)
    
    # If RAG context is missing or thin, supplement with section summaries
    if "No relevant context found" in rag_context or len(rag_context) < 200:
        section_contexts = []
        for section_num, score in matching_sections:
            if score >= 0.3:
                ctx = get_section_context(section_num)
                if ctx:
                    section_contexts.append(ctx)
        
        if section_contexts:
            enhanced = "\n\n".join(section_contexts)
            if rag_context and "No relevant context found" not in rag_context:
                enhanced = rag_context + "\n\n=== ADDITIONAL SECTION REFERENCES ===\n\n" + enhanced
            return enhanced
    
    return rag_context


def answer_rti_query(query: str) -> Dict:
    """
    Main entry point for answering RTI queries.
    
    Combines rule-based, section mapping, and RAG approaches.
    
    Args:
        query: User's RTI-related question.
    
    Returns:
        Dict with: answer, section, confidence, source
    """
    # Step 1: Check rule-based answers first (highest priority)
    rule_answer = check_rule_based_answer(query)
    if rule_answer:
        return rule_answer
    
    # Step 2: Find matching sections
    matching_sections = find_matching_sections(query)
    
    if matching_sections and matching_sections[0][1] >= 0.5:
        best_section = matching_sections[0][0]
        section_data = RTI_SECTION_MAP[best_section]
        
        return {
            "answer": section_data["summary"],
            "section": best_section,
            "confidence": round(matching_sections[0][1], 2),
            "source": "knowledge_base",
            "related_sections": [s[0] for s in matching_sections[1:4]]
        }
    
    # Step 3: Return guidance for LLM to use RAG
    return {
        "answer": None,  # Signal to use RAG/LLM
        "section": None,
        "confidence": 0.0,
        "source": "rag_required",
        "suggested_sections": [s[0] for s in matching_sections] if matching_sections else []
    }

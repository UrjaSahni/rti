"""
Appeal Agent — drafts first appeal letters under Section 19(1) RTI Act 2005.

CONDITIONAL APPEAL GENERATION:
- ALLOWED:     NO appeal generated — information was provided
- PARTIAL:     Appeal for incomplete information
- NO_RESPONSE: Appeal citing deemed refusal under Section 7(2)
- REJECTED/DENIED: Appeal challenging improper exemption use

Uses response_text + classification to generate appeal letters.
"""
from datetime import date, timedelta
from typing import Dict, Optional

from groq import Groq
from openai import OpenAI

from app.config import settings
from app.utils.prompt_templates import APPEAL_DRAFT_PROMPT


# ══════════════════════════════════════════════════════════════════════════════
# LLM CALLING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _call_groq(prompt: str) -> str:
    """Call Groq API (llama-3.3-70b-versatile) for appeal drafting."""
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    """Call OpenAI API (gpt-4o-mini) as fallback."""
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()


def _call_llm(prompt: str) -> str:
    """Call Groq; fall back to OpenAI on any exception."""
    try:
        return _call_groq(prompt)
    except Exception as groq_err:
        print(f"[appeal_agent] Groq failed ({groq_err}). Falling back to OpenAI...")
        try:
            return _call_openai(prompt)
        except Exception as oai_err:
            raise RuntimeError(
                f"Both LLMs failed. Groq: {groq_err} | OpenAI: {oai_err}"
            )


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _get_user_details(
    appellant_name: Optional[str] = None,
    appellant_address: Optional[str] = None,
) -> Dict[str, str]:
    """Return user details with placeholders if not provided."""
    return {
        "name": appellant_name.strip() if appellant_name else "[Your Name]",
        "address": appellant_address.strip() if appellant_address else "[Your Address]",
    }


def _get_rti_details(
    department_name: Optional[str] = None,
    rti_subject: Optional[str] = None,
    date_filed: Optional[str] = None,
) -> Dict[str, str]:
    """Return RTI details with placeholders if not provided."""
    return {
        "department": department_name.strip() if department_name else "[Department Name]",
        "subject": rti_subject.strip() if rti_subject else "Information requested under RTI Act 2005",
        "date_filed": date_filed.strip() if date_filed else "[Date of RTI Filing]",
    }


def _format_appeal_letter(
    appeal_authority: str,
    user: Dict[str, str],
    rti: Dict[str, str],
    grounds: str,
    specific_points: str,
    relief_sought: str,
) -> str:
    """
    Format a formal first appeal letter with proper legal structure.
    
    Args:
        appeal_authority: Title of the First Appellate Authority
        user: Dict with 'name' and 'address'
        rti: Dict with 'department', 'subject', 'date_filed'
        grounds: Legal grounds for appeal
        specific_points: Specific points of contention
        relief_sought: What relief the appellant seeks
    
    Returns:
        Formatted appeal letter string
    """
    today = date.today().strftime("%d %B %Y")
    
    letter = f"""
FIRST APPEAL UNDER SECTION 19(1) OF THE RIGHT TO INFORMATION ACT, 2005

Date: {today}

To,
The {appeal_authority}
{rti['department']}
[Office Address]

Subject: First Appeal against the response/non-response of the Public Information Officer
         regarding RTI Application dated {rti['date_filed']}

Reference: RTI Application dated {rti['date_filed']} — "{rti['subject']}"

Respected Sir/Madam,

I, {user['name']}, the undersigned, hereby file this First Appeal under Section 19(1) 
of the Right to Information Act, 2005, against the response/non-response of the 
Public Information Officer (PIO) of {rti['department']}.

GROUNDS FOR APPEAL:
{grounds}

SPECIFIC POINTS OF CONTENTION:
{specific_points}

RELIEF SOUGHT:
{relief_sought}

LEGAL BASIS:
This appeal is filed in accordance with Section 19(1) of the RTI Act, 2005, which 
provides that any person who does not receive a decision within the specified time 
or is aggrieved by a decision of the PIO may file an appeal to the First Appellate 
Authority within 30 days of receipt of such decision or expiry of the time limit.

I request that this appeal be heard and decided within the statutory period of 30 days 
as prescribed under Section 19(6) of the RTI Act, 2005.

I affirm that the statements made in this appeal are true to the best of my knowledge 
and belief.

Thanking you,

Yours faithfully,

{user['name']}
{user['address']}
[Contact Number]
[Email Address]

Enclosures:
1. Copy of original RTI application dated {rti['date_filed']}
2. Copy of PIO's response (if any)
3. Any other relevant documents
""".strip()
    
    return letter


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE-TYPE SPECIFIC GENERATORS
# ══════════════════════════════════════════════════════════════════════════════

def generate_allowed_response() -> Dict:
    """
    Handle ALLOWED classification — NO appeal required.
    
    When response says "information enclosed", "documents attached", etc.,
    the RTI request was fulfilled. DO NOT generate an appeal.
    
    Returns:
        Dict with type="no_appeal" and appropriate message
    """
    return {
        "type": "no_appeal",
        "message": (
            "No First Appeal is required as the requested information has been provided."
        ),
        "suggestion": (
            "If you believe the information is incomplete or incorrect, you may still "
            "file an appeal under Section 19(1) of the RTI Act, 2005 within 30 days. "
            "However, based on the response classification, no appeal appears necessary."
        ),
        "legal_reference": "Section 7(1) — Information provided within stipulated time.",
    }


def generate_partial_appeal(
    response_text: str,
    user: Dict[str, str],
    rti: Dict[str, str],
) -> Dict:
    """
    Generate appeal for PARTIAL response — incomplete information provided.
    
    Grounds:
    - Incomplete information
    - Missing documents
    - Unsatisfactory response
    
    Args:
        response_text: The government's partial response
        user: User details dict
        rti: RTI details dict
    
    Returns:
        Dict with type="appeal_letter" and formatted content
    """
    grounds = """
The PIO has provided only partial information in response to my RTI application. 
The information furnished is incomplete and does not fully address the points 
raised in my original application. This partial disclosure violates the 
obligation under Section 7(1) of the RTI Act, 2005, which mandates providing 
complete information to the applicant.
""".strip()

    # Extract key points from response for specific contentions
    response_summary = response_text[:300] if response_text else "Partial response received"
    
    specific_points = f"""
1. The PIO's response dated [Date of Response] provides only partial information.

2. The following aspects of my RTI application remain unanswered:
   - [Specific point 1 not addressed]
   - [Specific point 2 not addressed]
   - [Missing documents/records]

3. Summary of PIO's response: "{response_summary}..."

4. The partial response does not satisfy the requirements of a complete disclosure 
   under the RTI Act.

5. No valid reason under Section 8 or Section 9 has been cited for withholding 
   the remaining information.
""".strip()

    relief_sought = """
1. Direct the PIO to provide the complete information as requested in my original 
   RTI application.

2. Provide copies of all documents/records that were not furnished in the 
   initial response.

3. If any information is to be denied, provide specific reasons citing the 
   applicable exemption clauses under Section 8 or Section 9.

4. Award compensation for the delay and inconvenience caused, if deemed appropriate 
   under Section 19(8)(b).
""".strip()

    appeal_letter = _format_appeal_letter(
        appeal_authority="First Appellate Authority",
        user=user,
        rti=rti,
        grounds=grounds,
        specific_points=specific_points,
        relief_sought=relief_sought,
    )

    return {
        "type": "appeal_letter",
        "content": appeal_letter,
        "classification": "PARTIAL",
        "grounds_summary": "Incomplete information — PIO provided partial response only.",
        "legal_reference": "Section 19(1) read with Section 7(1) of RTI Act, 2005",
        "deadline": (date.today() + timedelta(days=30)).strftime("%d %B %Y"),
    }


def generate_no_response_appeal(
    user: Dict[str, str],
    rti: Dict[str, str],
) -> Dict:
    """
    Generate appeal for NO_RESPONSE — deemed refusal under Section 7(2).
    
    Grounds:
    - No response within 30 days
    - Deemed refusal under Section 7(2)
    
    Args:
        user: User details dict
        rti: RTI details dict
    
    Returns:
        Dict with type="appeal_letter" and formatted content
    """
    grounds = """
The Public Information Officer (PIO) has failed to provide any response to my 
RTI application within the statutory period of 30 days as mandated under 
Section 7(1) of the Right to Information Act, 2005.

As per Section 7(2) of the RTI Act, 2005:
"If the Central Public Information Officer or State Public Information Officer, 
as the case may be, fails to give decision on the request for information within 
the period specified under sub-section (1), the Central Public Information Officer 
or State Public Information Officer, as the case may be, shall be deemed to have 
refused the request."

This non-response constitutes a DEEMED REFUSAL and I am entitled to file this 
First Appeal under Section 19(1) of the Act.
""".strip()

    specific_points = f"""
1. My RTI application was filed on {rti['date_filed']}.

2. Subject of RTI: "{rti['subject']}"

3. More than 30 days have elapsed since the date of filing, and no response 
   has been received from the PIO.

4. No intimation regarding extension of time under Section 7(3) was received.

5. No transfer intimation under Section 6(3) was received.

6. This complete non-response is a violation of the statutory obligation of 
   the PIO under the RTI Act, 2005.

7. The PIO may also be liable for penalty under Section 20 of the RTI Act for 
   failing to furnish information without reasonable cause.
""".strip()

    relief_sought = """
1. Direct the PIO to immediately provide the information sought in my RTI 
   application dated {date_filed}.

2. Take cognizance of the deemed refusal under Section 7(2) and issue appropriate 
   directions to the PIO.

3. Initiate penalty proceedings against the PIO under Section 20 of the RTI Act 
   for failure to furnish information without reasonable cause.

4. Award compensation for mental agony, harassment, and inconvenience caused 
   by the non-response, as provided under Section 19(8)(b).

5. Ensure compliance within the statutory period of 30 days as per Section 19(6).
""".format(date_filed=rti['date_filed']).strip()

    appeal_letter = _format_appeal_letter(
        appeal_authority="First Appellate Authority",
        user=user,
        rti=rti,
        grounds=grounds,
        specific_points=specific_points,
        relief_sought=relief_sought,
    )

    return {
        "type": "appeal_letter",
        "content": appeal_letter,
        "classification": "NO_RESPONSE",
        "grounds_summary": "Deemed refusal — no response received within 30 days.",
        "legal_reference": "Section 19(1) read with Section 7(2) of RTI Act, 2005",
        "deadline": (date.today() + timedelta(days=30)).strftime("%d %B %Y"),
    }


def generate_rejection_appeal(
    response_text: str,
    user: Dict[str, str],
    rti: Dict[str, str],
) -> Dict:
    """
    Generate appeal for REJECTED/DENIED — challenge improper use of exemptions.
    
    Grounds:
    - Improper use of exemptions (Section 8/9)
    - Lack of justification
    - Overbroad exemption claims
    
    Args:
        response_text: The government's rejection response
        user: User details dict
        rti: RTI details dict
    
    Returns:
        Dict with type="appeal_letter" and formatted content
    """
    grounds = """
The Public Information Officer (PIO) has wrongfully denied/rejected my RTI 
application by invoking exemptions under Section 8 and/or Section 9 of the 
Right to Information Act, 2005, without adequate justification.

I submit that the denial is improper on the following grounds:

a) The information sought does not fall within any of the exemption clauses 
   under Section 8(1)(a) to (j) of the RTI Act.

b) The PIO has failed to demonstrate how disclosure of the requested information 
   would cause harm as required under Section 8.

c) The exemption, if any, should have been applied narrowly. The PIO should have 
   severed the exempt portions and provided the remaining information as mandated 
   under Section 10 of the RTI Act.

d) Even if the information falls under an exemption, it may still be disclosed 
   if the public interest in disclosure outweighs the harm to protected interests, 
   as provided under the proviso to Section 8(1).
""".strip()

    response_summary = response_text[:300] if response_text else "Request denied/rejected"
    
    specific_points = f"""
1. PIO's response summary: "{response_summary}..."

2. The exemption clause(s) cited by the PIO (if any) are not applicable to the 
   information requested.

3. The PIO has not provided specific reasons for denial as required under 
   Section 7(8) of the RTI Act.

4. The denial appears to be a blanket rejection without proper application of 
   mind to each point raised in my RTI application.

5. The PIO has failed to invoke the severability clause under Section 10 to 
   provide non-exempt portions of the information.

6. There is significant public interest in the disclosure of this information 
   which outweighs any claimed exemption.
""".strip()

    relief_sought = """
1. Set aside the wrongful denial/rejection by the PIO.

2. Direct the PIO to provide the complete information sought in my RTI application.

3. If any portion of the information is genuinely exempt, direct the PIO to:
   a) Clearly specify the exemption clause and its applicability
   b) Provide a detailed justification for the exemption
   c) Sever the exempt portion and provide the remaining information

4. Initiate penalty proceedings against the PIO under Section 20 if the denial 
   is found to be without reasonable cause or in bad faith.

5. Award compensation for the delay, mental agony, and inconvenience caused.
""".strip()

    appeal_letter = _format_appeal_letter(
        appeal_authority="First Appellate Authority",
        user=user,
        rti=rti,
        grounds=grounds,
        specific_points=specific_points,
        relief_sought=relief_sought,
    )

    return {
        "type": "appeal_letter",
        "content": appeal_letter,
        "classification": "REJECTED",
        "grounds_summary": "Improper denial — exemptions cited without adequate justification.",
        "legal_reference": "Section 19(1) read with Section 8, 9, 10 of RTI Act, 2005",
        "deadline": (date.today() + timedelta(days=30)).strftime("%d %B %Y"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONDITIONAL APPEAL GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def run_appeal_agent(
    response_text: str,
    classification: str,
    appellant_name: Optional[str] = None,
    appellant_address: Optional[str] = None,
    department_name: Optional[str] = None,
    rti_subject: Optional[str] = None,
    date_filed: Optional[str] = None,
) -> Dict:
    """
    CONDITIONAL First Appeal Generator based on response classification.
    
    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  CRITICAL LOGIC: Generate appeal ONLY when required                      ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║  ALLOWED    → NO appeal (info provided) → return type="no_appeal"        ║
    ║  PARTIAL    → Appeal for incomplete info                                 ║
    ║  NO_RESPONSE→ Appeal citing deemed refusal (Section 7(2))                ║
    ║  REJECTED   → Appeal challenging improper exemptions                     ║
    ║  DENIED     → Same as REJECTED                                           ║
    ╚══════════════════════════════════════════════════════════════════════════╝
    
    IMPORTANT CONSTRAINTS:
    - DO NOT assume missing info if response says "information enclosed"
    - DO NOT include false claims
    - Match appeal content strictly with response type
    - Use formal legal tone

    Args:
        response_text: The government response text.
        classification: Response classification (ALLOWED, PARTIAL, NO_RESPONSE, 
                        REJECTED, DENIED, TRANSFERRED).
        appellant_name: User's name (optional). Defaults to "[Your Name]".
        appellant_address: User's address (optional). Defaults to "[Your Address]".
        department_name: Department name (optional). Defaults to "[Department Name]".
        rti_subject: Subject of original RTI (optional).
        date_filed: Date RTI was filed (optional).

    Returns:
        Dict with either:
        - type="no_appeal", message=... (for ALLOWED)
        - type="appeal_letter", content=... (for PARTIAL/NO_RESPONSE/REJECTED/DENIED)
    """
    # Normalize classification
    response_type = classification.upper().strip()
    
    # Get user and RTI details (with placeholders if not provided)
    user = _get_user_details(appellant_name, appellant_address)
    rti = _get_rti_details(department_name, rti_subject, date_filed)
    
    # ══════════════════════════════════════════════════════════════════════════
    # CONDITIONAL APPEAL GENERATION
    # ══════════════════════════════════════════════════════════════════════════
    
    # ──────────────────────────────────────────────────────────────────────────
    # CASE 1: ALLOWED — Information was provided, NO appeal required
    # ──────────────────────────────────────────────────────────────────────────
    if response_type == "ALLOWED":
        # DO NOT generate appeal if response says "information enclosed" etc.
        return generate_allowed_response()
    
    # ──────────────────────────────────────────────────────────────────────────
    # CASE 2: PARTIAL — Incomplete information, generate appeal
    # ──────────────────────────────────────────────────────────────────────────
    elif response_type == "PARTIAL":
        return generate_partial_appeal(response_text, user, rti)
    
    # ──────────────────────────────────────────────────────────────────────────
    # CASE 3: NO_RESPONSE — Deemed refusal under Section 7(2)
    # ──────────────────────────────────────────────────────────────────────────
    elif response_type == "NO_RESPONSE":
        return generate_no_response_appeal(user, rti)
    
    # ──────────────────────────────────────────────────────────────────────────
    # CASE 4: REJECTED/DENIED — Challenge improper exemptions
    # ──────────────────────────────────────────────────────────────────────────
    elif response_type in ("REJECTED", "DENIED"):
        return generate_rejection_appeal(response_text, user, rti)
    
    # ──────────────────────────────────────────────────────────────────────────
    # CASE 5: TRANSFERRED — Generate appeal for non-response from transferee
    # ──────────────────────────────────────────────────────────────────────────
    elif response_type == "TRANSFERRED":
        # Treat as NO_RESPONSE if no reply from transferred department
        result = generate_no_response_appeal(user, rti)
        result["classification"] = "TRANSFERRED"
        result["grounds_summary"] = (
            "Application transferred under Section 6(3) but no response received "
            "from transferee department within stipulated period."
        )
        return result
    
    # ──────────────────────────────────────────────────────────────────────────
    # DEFAULT: Unknown classification — return error
    # ──────────────────────────────────────────────────────────────────────────
    else:
        return {
            "type": "error",
            "message": f"Unknown classification: {classification}. Valid values: "
                       "ALLOWED, PARTIAL, NO_RESPONSE, REJECTED, DENIED, TRANSFERRED.",
        }


# Legacy function for backward compatibility
def _determine_grounds(response_type: str) -> str:
    """
    Determine the legal grounds for appeal based on the PIO's response type.
    (Kept for backward compatibility)
    """
    grounds_map = {
        "DENIED": (
            "The PIO has wrongfully denied the requested information by invoking "
            "exemptions under Section 8 without adequate justification."
        ),
        "PARTIAL": (
            "The PIO has provided only partial information and withheld the remainder "
            "without valid grounds."
        ),
        "NO_RESPONSE": (
            "The PIO has failed to respond within the statutory 30-day period prescribed "
            "under Section 7(1). This constitutes a deemed refusal under Section 7(2)."
        ),
        "TRANSFERRED": (
            "The application was transferred under Section 6(3) but no response has been "
            "received from the transferee department."
        ),
        "ALLOWED": (
            "Information was provided. No appeal is typically required."
        ),
    }
    return grounds_map.get(
        response_type,
        "The PIO's response does not comply with the provisions of the RTI Act 2005."
    )


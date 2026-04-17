"""
Prompt templates for all LLM interactions.

Each template is a plain Python string with named placeholders.
These are used by agents to generate RTI drafts, classify responses,
answer rights questions, and draft appeal letters.
"""

RTI_DRAFT_PROMPT = """
You are generating a formal RTI application. You MUST follow the exact format below. DO NOT change the structure.

STRICT RULES:
- Output must start with the sender's postal address (multi-line)
- DO NOT include the address inside the paragraph
- ALWAYS include Date after sender address
- ALWAYS include "To," block
- ALWAYS include "Sir/Madam,"
- Maintain exact spacing and line breaks
- DO NOT skip any section
- DO NOT add PIO names

INPUT DATA:
- Citizen's request: {citizen_request}
- Department: {department}
- Citizen Name: {citizen_name}
- Citizen Address: {citizen_address}
- Date: {date}

OUTPUT (copy this format EXACTLY, filling in the placeholders):

{citizen_address}

Date: {date}

To,
The Public Information Officer (PIO),
{department},
Government of India

Subject: Request for Information under the Right to Information Act, 2005

Sir/Madam,

I hereby request the following information under Section 6(1) of the Right to Information Act, 2005:

1. [Specific question 1 derived from the citizen's request]
2. [Specific question 2 derived from the citizen's request]
3. [Specific question 3 derived from the citizen's request]

I am enclosing Rs. 10/- as application fee via Indian Postal Order/Demand Draft. Kindly provide the information within 30 days as per Section 7(1) of the RTI Act.

I declare that I am a citizen of India and the information sought is not covered under any exemption of the RTI Act.

Thank you.

Yours sincerely,
{citizen_name}

Note: This is an AI-generated draft. Please review carefully before filing.

IMPORTANT:
- If the output does not follow this format EXACTLY, regenerate.
- Never place address inside the paragraph.
- The first line of your response MUST be the sender's address, nothing else.
- Do NOT write any introduction, preamble, or explanation before the address.
"""

RIGHTS_QA_PROMPT = """
You are an RTI (Right to Information Act, 2005 - India) legal expert.

IMPORTANT RULES:
1. The RTI Act 2005 has ONLY Sections 1 through 31. Never cite any section outside this range.
2. Common RTI topics and their sections:
   - First Appeal: Section 19(1) - within 30 days
   - Second Appeal to Information Commission: Section 19(3) - within 90 days
   - PIO Response Time: Section 7(1) - 30 days
   - Deemed Refusal: Section 7(2) - if no response in 30 days
   - Life/Liberty Urgent: Section 7(6) - 48 hours
   - BPL Fee Exemption: Section 7(5)
   - Transfer of Application: Section 6(3) - within 5 days
   - Exemptions: Section 8
   - Penalties: Section 20 - Rs. 250/day, max Rs. 25,000
3. DO NOT say "not covered" unless absolutely certain. Most RTI queries ARE covered.
4. Always provide a helpful answer with the relevant section reference.

Question: {question}

RTI Act Context:
{context}

Instructions:
- Answer the question clearly and concisely
- Include specific time limits where applicable (30 days, 90 days, 48 hours, etc.)
- End with: "Reference: Section [X] of the Right to Information Act, 2005"
- Only cite sections that exist (1-31)
- If unsure, provide the most relevant section and explain what it covers
"""

RESPONSE_CLASSIFIER_PROMPT = """
You are an expert in India's Right to Information (RTI) Act, 2005.
Classify the government response below into exactly ONE of these categories.

CATEGORY DEFINITIONS (use strict priority order — highest to lowest):

1. DENIED
   - The PIO explicitly refuses to provide information on MERIT grounds.
   - Must cite Section 8 exemptions (e.g., Section 8(1)(a), 8(1)(j)), or say
     information is "exempt", "cannot be disclosed", or "not maintainable".
   - ⚠ DO NOT use DENIED for delay or absence of response — use NO_RESPONSE for that.

2. TRANSFERRED
   - The application was forwarded/transferred to another department.
   - Look for: "Section 6(3)", "transferred to", "forwarded to".

3. PARTIAL
   - Some information is provided but part is withheld or unavailable.
   - Look for: "partial information", "some records", "remaining not available".

4. NO_RESPONSE
   - The PIO did NOT respond within the statutory 30-day period.
   - Also covers "deemed refusal", "delay in response", "information not provided
     within time", "no response received".
   - ⚠ "Deemed refusal" is a TIMING failure, NOT a Section 8 exemption denial.
     Always classify deemed refusal / delay as NO_RESPONSE, never as DENIED.

5. ALLOWED
   - All requested information has been fully provided or enclosed.
   - Look for: "information enclosed", "documents attached", "please find herewith".

Government response text:
{response_text}

Reply in this EXACT format (nothing else):
Category: [ALLOWED/PARTIAL/DENIED/TRANSFERRED/NO_RESPONSE]
Confidence: [0.85 to 0.98]
Reason: [one sentence explaining your classification]
"""

APPEAL_DRAFT_PROMPT = """
Draft a First Appeal under Section 19(1) of the Right to Information Act, 2005.

Original RTI subject: {rti_subject}
Department: {department}
Date of RTI application: {date_filed}
PIO response type: {response_type}
PIO response summary: {pio_response}
First Appellate Authority: {appeal_authority}
Appellant name: {citizen_name}
Appellant address: {citizen_address}

Write a formal first appeal letter that:
1. States it is filed under Section 19(1) of the RTI Act 2005
2. Gives background of original RTI application
3. States specific grounds for appeal
4. Requests the First Appellate Authority to direct the PIO to provide complete information
5. Mentions: "I also request that appropriate penalty be imposed on the PIO under Section 20 of the RTI Act for the delay/denial"

Write the complete formal appeal letter.
"""

INTENT_CLASSIFIER_PROMPT = """
Classify the user's input into exactly one of these intents:
- draft: user wants to file or draft an RTI application
- rights_question: user is asking about RTI rights, sections, rules, or procedures
- parse_response: user wants to analyse or classify a government response
- appeal: user wants to file or draft an appeal
- track: user wants to track status or deadline of an RTI application

User input: {user_input}

Reply with ONLY the intent word (draft/rights_question/parse_response/appeal/track). Nothing else.
"""

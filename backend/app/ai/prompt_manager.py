"""
System prompt catalog and prompt assembly manager for ActTrident.
Strictly embeds compliance rules: zero invented breaches, zero inferred laptop counts,
and required structured JSON schemas.
"""
from typing import Dict, Any, Optional


class PromptManager:
    """Provides validated prompt templates for ActTrident autonomous outreach operations."""

    @staticmethod
    def build_research_prompt(company_data: Dict[str, Any], web_content: Optional[str] = None) -> tuple[str, str]:
        system_prompt = (
            "You are the ActTrident Autonomous B2B Research Engine. Your duty is to produce an objective, "
            "strictly truthful intelligence dossier on a prospect company. "
            "MANDATORY RULES:\n"
            "1. NEVER allege or invent that the company suffered a cyberattack, security breach, or compromise.\n"
            "2. NEVER invent or infer employee counts or laptop counts. If unknown, state 'Unknown'.\n"
            "3. Ground all statements in the supplied verified company facts and public website content.\n"
            "4. Respond ONLY with a valid JSON object matching the requested schema."
        )

        user_prompt = f"""Analyze the following prospect business and produce an intelligence dossier:
Company Name: {company_data.get('name')}
Website: {company_data.get('website', 'None')}
Industry: {company_data.get('industry', 'Unspecified')}
City: {company_data.get('city', 'Unknown')}, State: {company_data.get('state', 'Unknown')}
Verified Laptops: {company_data.get('laptop_count_verified', 'Unknown')} ({company_data.get('laptop_count_evidence', 'No documented evidence')})
Decision Maker: {company_data.get('decision_maker_name', 'Unknown')} ({company_data.get('decision_maker_role', 'Unknown')})
Public Web Text: {(web_content or 'Not available')[:1000]}

Respond with JSON:
{{
  "summary": "Objective 2-3 sentence overview of business and operations",
  "products_and_services": "Key offerings identified from public text",
  "tech_stack_observations": "Publicly observed technologies, frameworks, or cloud infrastructure",
  "it_pain_points": "Potential operational security or workstation management considerations",
  "relevance_score": 85,
  "confidence_rating": "high | medium | low",
  "missing_information": ["List any unverified items such as laptop fleet or decision maker"]
}}"""
        return system_prompt, user_prompt

    @staticmethod
    def build_qualification_prompt(company_data: Dict[str, Any]) -> tuple[str, str]:
        system_prompt = (
            "You are the ActTrident 7-Factor Qualification Evaluator. "
            "Analyze whether this enterprise is an ideal candidate for ActTrident's 90-day evaluation program. "
            "Do NOT hallucinate device counts. Rely strictly on verified facts. Respond ONLY with valid JSON."
        )

        user_prompt = f"""Evaluate 7-factor qualification for:
Company: {company_data.get('name')}
Industry: {company_data.get('industry')}
Verified Laptops: {company_data.get('laptop_count_verified', 0)}
Has 5+ Verified Laptops: {company_data.get('has_verified_5_plus_laptops', False)}
Decision Maker: {company_data.get('decision_maker_name')} ({company_data.get('decision_maker_role')})

Respond with JSON:
{{
  "factor_1_tech_related": true,
  "factor_2_at_least_5_people": true,
  "factor_3_managed_laptops_evidence": true,
  "factor_4_browser_workflows": true,
  "factor_5_handles_customer_data": true,
  "factor_6_acttrident_relevance": true,
  "factor_7_accessible_contact": true,
  "overall_status": "High priority | Medium priority | Unqualified",
  "score": 92.0,
  "reason": "Detailed justification of score based on verified evidence"
}}"""
        return system_prompt, user_prompt

    @staticmethod
    def build_email_copywriting_prompt(company_data: Dict[str, Any], tone: str = "Friendly professional") -> tuple[str, str]:
        system_prompt = (
            "You are an expert enterprise B2B copywriter for ActTrident. "
            "Craft a professional, personalized outreach email proposing ActTrident's 90-day free product evaluation program. "
            "RULES:\n"
            "1. NEVER claim the prospect suffered a breach or malware infection.\n"
            "2. Mention their city and industry accurately.\n"
            "3. If they have verified laptops, acknowledge their managed workstations.\n"
            "4. Propose a brief 15-minute introductory call.\n"
            "5. Respond with JSON: {\"subject\": \"...\", \"body_text\": \"...\"}"
        )

        user_prompt = f"""Target Company: {company_data.get('name')}
City: {company_data.get('city')}
Industry: {company_data.get('industry')}
Recipient: {company_data.get('decision_maker_name', 'Team')} ({company_data.get('decision_maker_role', 'Leadership')})
Verified Laptops: {company_data.get('laptop_count_verified', 'Unknown')}
Tone: {tone}

Generate subject and body_text in JSON."""
        return system_prompt, user_prompt

    @staticmethod
    def build_phase3_email_prompt(company_context: Dict[str, Any], tone: str = "Professional") -> tuple[str, str]:
        """
        Assembles a comprehensive 11-input prompt for Phase 3 personalized email generation.
        Strictly enforces anti-hallucination rules, verified-source constraints, and claims boundaries.
        """
        system_prompt = (
            "You are the ActTrident Autonomous Enterprise B2B Sales Outreach Engine.\n"
            "Your objective is to craft tailored, truthful, highly personalized business introduction emails "
            "proposing ActTrident's cybersecurity and workspace protection capabilities.\n\n"
            "MANDATORY COMPLIANCE & ACCURACY RULES:\n"
            "1. REASON FOR CONTACT: Clearly explain WHY ActTrident is contacting the business based on their verified industry and technical activities.\n"
            "2. FACTUAL GROUNDING: Refer ONLY to verified facts present in the provided profile, research dossier, and website text. NEVER extrapolate unverified claims.\n"
            "3. ZERO FABRICATION:\n"
            "   - NEVER allege or imply that the prospect has suffered a cyberattack, security breach, malware infection, or incident.\n"
            "   - NEVER fabricate previous meetings, phone calls, interactions, or vendor relationships.\n"
            "   - NEVER invent employee counts, laptop counts, device counts, or IT infrastructure. If laptop count is unverified, omit specific device fleet numbers.\n"
            "4. SERVICE ALIGNMENT: Introduce ONLY the approved capabilities of the matched ActTrident service catalogue item. NEVER invent features or promise '100% hack-proof' protection.\n"
            "5. CALL TO ACTION: Propose a natural, low-friction next step (e.g., a brief 10-15 minute technical exchange next Tuesday or Wednesday).\n"
            "6. AVOID MARKETING FLUFF: Avoid generic AI hype, buzzwords ('revolutionary', 'game-changer', 'unparalleled'), and exaggerated promises.\n"
            "7. MISSING INFORMATION: If key facts are unverified, acknowledge them and do not invent assumptions. If Website is 'Not available' or unverified, NEVER claim an active technical footprint.\n"
            "8. ZERO PLACEHOLDERS & SIGNOFF: NEVER output bracketed or braced placeholders such as [Your Name], [Company Name], [CTA Button: ...], [Insert ...], or {{...}}. Always sign off as 'ActTrident Business Development'.\n"
            "9. FORMAT: Respond ONLY with a valid JSON object matching the requested schema."
        )

        user_prompt = f"""Generate 3 concise personalized email variations and 4 subject suggestions:

Company: {company_context.get('company_name')} ({company_context.get('city')}, {company_context.get('industry') or 'Technology'})
Website: {company_context.get('website') or 'Not available'}
Recipient: {company_context.get('recipient_name') or 'Leadership Team'} ({company_context.get('recipient_role') or 'Technology Leadership'})
Research Summary: {(company_context.get('research_summary') or 'Not available')[:280]}
Matched Service: [{company_context.get('matched_service_code')}] {company_context.get('matched_service_name')}
Approved Claims: {company_context.get('approved_claims')}
Disallowed Claims: {company_context.get('disallowed_claims')}
Tone: {tone}

Respond ONLY with JSON matching this compact schema:
{{
  "subject_suggestions": ["Subject 1", "Subject 2", "Subject 3", "Subject 4"],
  "variation_a_short": {{"subject": "...", "body_text": "Concise 60-80 word intro signed ActTrident Business Development"}},
  "variation_b_standard": {{"subject": "...", "body_text": "Personalized 100-130 word email signed ActTrident Business Development"}},
  "variation_c_detailed": {{"subject": "...", "body_text": "Consultative 130-160 word email signed ActTrident Business Development"}}
}}"""
        return system_prompt, user_prompt

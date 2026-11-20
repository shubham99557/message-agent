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

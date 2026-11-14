# ActTrident AI Outreach Agent - AI Provider Configuration Guide

The ActTrident platform features a **pluggable, provider-independent AI architecture** supporting Google Gemini API, OpenAI-compatible APIs, Anthropic, or an offline deterministic fallback engine.

---

## 1. Supported Providers

### 1. Google Gemini API (Recommended)
- **Settings Key**: `AI_PROVIDER="gemini"`
- **Environment Variable**: `GEMINI_API_KEY="AIzaSy..."`
- **Supported Models**: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`
- **Capabilities**: Used for multi-factor lead qualification, deep company research dossiers, 5-tone email personalization, and 10-class inbound reply categorization.

### 2. OpenAI-Compatible API Endpoints
- **Settings Key**: `AI_PROVIDER="openai"`
- **Environment Variable**: `OPENAI_API_KEY="sk-..."`
- **Base URL Variable**: `OPENAI_BASE_URL="https://api.openai.com/v1"`
- **Supported Models**: `gpt-4o-mini`, `gpt-4o`, or any local OpenAI-compatible endpoint (such as vLLM or Ollama).

### 3. Built-in Deterministic Engine (Offline / Test Mode)
- **Settings Key**: `AI_PROVIDER="mock"`
- **Zero API keys required**: Completely functional out-of-the-box.
- Implements strict ActTrident business logic, 7-factor qualification scoring, 5 personalized email styles, and 10-class regex/NLP reply classification with zero external network dependencies.

---

## 2. Anti-Hallucination & Truth Guardrails

> [!CAUTION]
> Per ActTrident operating principles, the AI layer is programmatically restricted by the following guardrails:
> 1. **No Invented Breaches**: The AI is strictly barred from fabricating cyberattacks or security incidents about a prospect.
> 2. **Laptop Fleet Evidence**: The AI will never score a company as having 5+ laptops unless verifiable public evidence or company confirmation is documented.
> 3. **Non-Deceptive Subjects**: Never uses deceptive subject prefixes (such as fake familiarity or simulated replies) when no prior contact took place.
> 4. **Prompt Injection Shielding**: External website content is sanitized and delimited using untrusted content filters before LLM ingestion.

"""
ActTrident Local AI Brain & Gateway Module.
Local-first, provider-abstracted inference engine powering Autonomous Outreach.
"""
from app.ai.base import BaseAIProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.model_manager import AIModelManager, RECOMMENDED_LOCAL_MODELS
from app.ai.prompt_manager import PromptManager
from app.ai.health_check import get_local_ai_health
from app.ai.local_ai_gateway import local_ai_gateway, LocalAIGateway

__all__ = [
    "BaseAIProvider",
    "OllamaProvider",
    "AIModelManager",
    "PromptManager",
    "get_local_ai_health",
    "local_ai_gateway",
    "LocalAIGateway",
    "RECOMMENDED_LOCAL_MODELS",
]

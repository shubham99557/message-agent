"""
Abstract base class and contract for all ActTrident AI providers.
Enforces local-first execution, structured JSON generation, and diagnostic health reporting.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseAIProvider(ABC):
    """Abstract interface for local and external AI model providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'ollama', 'deterministic', 'openai')."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """Generates plain text response given user and optional system prompts."""
        pass

    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generates validated structured JSON output."""
        pass

    @abstractmethod
    async def check_health(self) -> Dict[str, Any]:
        """Performs connection, model availability, and latency health check."""
        pass

    @abstractmethod
    async def list_models(self) -> List[Dict[str, Any]]:
        """Returns list of installed/available models on the provider."""
        pass

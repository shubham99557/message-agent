"""
Model lifecycle, metadata, and hardware-fit recommendation manager for ActTrident.
"""
import logging
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger("acttrident.ai.model_manager")

RECOMMENDED_LOCAL_MODELS = [
    {
        "tag": "llama3.2:latest",
        "name": "Llama 3.2 (3B Instruct)",
        "parameters": "3.2B",
        "quantization": "Q4_K_M",
        "size_gb": 2.01,
        "vram_required_gb": 2.5,
        "recommended_for": "Primary Choice: Fits 100% into 4GB VRAM (GTX 1650), ~48 tok/s",
        "supports_json": True,
        "supports_tools": True,
    },
    {
        "tag": "qwen2.5:1.5b",
        "name": "Qwen 2.5 (1.5B Instruct)",
        "parameters": "1.54B",
        "quantization": "Q4_K_M",
        "size_gb": 0.98,
        "vram_required_gb": 1.5,
        "recommended_for": "Ultra-lightweight fallback for low memory / battery saving",
        "supports_json": True,
        "supports_tools": True,
    },
    {
        "tag": "qwen2.5:3b",
        "name": "Qwen 2.5 (3B Instruct)",
        "parameters": "3.09B",
        "quantization": "Q4_K_M",
        "size_gb": 1.95,
        "vram_required_gb": 2.4,
        "recommended_for": "High-accuracy multilingual research and reasoning",
        "supports_json": True,
        "supports_tools": True,
    },
    {
        "tag": "gemma2:2b",
        "name": "Gemma 2 (2B Instruct)",
        "parameters": "2.61B",
        "quantization": "Q4_K_M",
        "size_gb": 1.63,
        "vram_required_gb": 2.0,
        "recommended_for": "Fast Google-designed lightweight model",
        "supports_json": True,
        "supports_tools": False,
    },
]


class AIModelManager:
    """Manages local AI model selection, inventory, and hardware suitability."""

    def __init__(self, active_model: Optional[str] = None):
        self._active_model = active_model or getattr(settings, "OLLAMA_MODEL", "llama3.2:latest")

    @property
    def active_model(self) -> str:
        return self._active_model

    def set_active_model(self, model_tag: str) -> str:
        """Updates the active model for subsequent inferences."""
        clean_tag = model_tag.strip()
        if not clean_tag:
            raise ValueError("Model tag cannot be empty.")
        self._active_model = clean_tag
        logger.info(f"ActTrident active local model switched to: {clean_tag}")
        return self._active_model

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Returns the recommended local model catalog with hardware profiles."""
        return RECOMMENDED_LOCAL_MODELS

    def get_model_profile(self, tag: str) -> Optional[Dict[str, Any]]:
        """Looks up profile metadata for a model tag."""
        for m in RECOMMENDED_LOCAL_MODELS:
            if m["tag"] == tag or tag.startswith(m["tag"].split(":")[0]):
                return m
        return None

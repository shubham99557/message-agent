"""
Native Ollama local AI provider for ActTrident.
Communicates strictly via localhost HTTP API (127.0.0.1:11434).
Never transmits prompts or data to cloud services.
"""
import json
import logging
import time
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.ai.base import BaseAIProvider

logger = logging.getLogger("acttrident.ai.ollama")


class OllamaProvider(BaseAIProvider):
    """Local Ollama client implementing BaseAIProvider."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self._base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self._default_model = default_model or getattr(settings, "OLLAMA_MODEL", "llama3.2:latest")
        self._timeout = timeout or float(getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 60))
        self._num_ctx = int(getattr(settings, "OLLAMA_NUM_CTX", 4096))

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def default_model(self) -> str:
        return self._default_model

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        target_model = model or self._default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": self._num_ctx,
            },
        }

        url = f"{self._base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 404:
                    raise FileNotFoundError(
                        f"Model '{target_model}' not found in local Ollama library. "
                        f"Run 'ollama pull {target_model}' to download it."
                    )
                res.raise_for_status()
                data = res.json()
                return data.get("response", "").strip()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to local Ollama service at {self._base_url}. "
                "Ensure Ollama is running ('ollama serve') on your Windows workstation."
            )
        except httpx.TimeoutException:
            raise TimeoutError(
                f"Local Ollama inference timed out after {self._timeout}s on model '{target_model}'."
            )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        expected_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generates structured JSON using Ollama's native JSON mode with fallback markdown cleanup."""
        target_model = model or self._default_model
        sys_directive = (system_prompt or "").strip()
        if sys_directive:
            sys_directive += "\nCRITICAL: Respond ONLY with a valid, parseable JSON object matching requirements. Do not wrap in conversational markdown."
        else:
            sys_directive = "CRITICAL: Respond ONLY with a valid JSON object. No conversational prose."

        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": sys_directive,
            "format": "json",
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": temperature,
                "num_predict": 700,
                "num_ctx": self._num_ctx,
            },
        }

        url = f"{self._base_url}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 404:
                    raise FileNotFoundError(
                        f"Model '{target_model}' not found in Ollama. Run 'ollama pull {target_model}'."
                    )
                res.raise_for_status()
                data = res.json()
                raw_text = data.get("response", "").strip()

                # Clean markdown fences if present
                clean_text = raw_text
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                elif clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                try:
                    parsed = json.loads(clean_text)
                except json.JSONDecodeError:
                    start_idx = clean_text.find("{")
                    end_idx = clean_text.rfind("}")
                    if start_idx != -1 and end_idx > start_idx:
                        parsed = json.loads(clean_text[start_idx:end_idx + 1])
                    else:
                        raise
                return parsed
        except json.JSONDecodeError as jde:
            logger.error(f"Failed to decode JSON from Ollama response: {raw_text[:200]}")
            raise ValueError(f"Ollama model '{target_model}' did not return valid JSON: {jde}")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to local Ollama service at {self._base_url}. "
                "Ensure Ollama is running on your Windows workstation."
            )
        except httpx.TimeoutException:
            raise TimeoutError(
                f"Local Ollama JSON inference timed out after {self._timeout}s on model '{target_model}'."
            )

    async def list_models(self) -> List[Dict[str, Any]]:
        """Lists all downloaded models from the local Ollama instance."""
        url = f"{self._base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                return data.get("models", [])
        except Exception as exc:
            logger.warning(f"Failed to query Ollama models: {exc}")
            return []

    async def check_model_exists(self, model_name: str) -> bool:
        """Verifies if a specific model tag is available in the local library."""
        models = await self.list_models()
        target = model_name.strip().lower()
        return any(target in (m.get("name") or "").lower() for m in models)

    async def check_health(self) -> Dict[str, Any]:
        """Performs a comprehensive diagnostic health check against local Ollama."""
        start = time.time()
        url = f"{self._base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(url)
                latency_ms = round((time.time() - start) * 1000, 2)
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    installed_names = [m.get("name", "") for m in models]
                    has_selected_model = any(
                        self._default_model in name or name in self._default_model
                        for name in installed_names
                    )
                    return {
                        "status": "healthy" if has_selected_model else "warning",
                        "provider": "ollama",
                        "endpoint": self._base_url,
                        "latency_ms": latency_ms,
                        "selected_model": self._default_model,
                        "selected_model_available": has_selected_model,
                        "installed_models_count": len(models),
                        "installed_models": installed_names,
                        "message": (
                            f"Ollama is running locally with {len(models)} installed model(s)."
                            if has_selected_model
                            else f"Ollama is running, but selected model '{self._default_model}' is not installed."
                        ),
                    }
                return {
                    "status": "degraded",
                    "provider": "ollama",
                    "endpoint": self._base_url,
                    "http_status": res.status_code,
                    "message": f"Ollama returned unexpected HTTP {res.status_code}.",
                }
        except httpx.ConnectError:
            return {
                "status": "offline",
                "provider": "ollama",
                "endpoint": self._base_url,
                "message": (
                    f"Ollama service is not reachable at {self._base_url}. "
                    "Start Ollama from the Windows Start menu or run 'ollama serve' in PowerShell."
                ),
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "ollama",
                "endpoint": self._base_url,
                "message": f"Ollama health check error: {str(exc)}",
            }

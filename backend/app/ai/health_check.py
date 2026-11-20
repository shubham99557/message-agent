"""
Health check and diagnostic telemetry service for ActTrident Local AI Brain.
"""
import logging
import time
from typing import Dict, Any, List
import httpx

from app.core.config import settings

logger = logging.getLogger("acttrident.ai.health")


async def get_local_ai_health(
    base_url: str = "http://127.0.0.1:11434",
    target_model: str = "llama3.2:latest",
) -> Dict[str, Any]:
    """
    Performs full health, model presence, active memory, and latency diagnostics
    for the local Ollama AI engine.
    """
    clean_url = base_url.rstrip("/")
    start_time = time.time()

    diag: Dict[str, Any] = {
        "provider": "ollama",
        "endpoint": clean_url,
        "selected_model": target_model,
        "is_online": False,
        "latency_ms": 0.0,
        "installed_models": [],
        "running_models": [],
        "model_ready": False,
        "status": "offline",
        "gpu_accelerated": True,
        "troubleshooting": None,
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            # 1. Tags check
            res_tags = await client.get(f"{clean_url}/api/tags")
            diag["latency_ms"] = round((time.time() - start_time) * 1000, 2)

            if res_tags.status_code == 200:
                diag["is_online"] = True
                models_data = res_tags.json().get("models", [])
                installed_names: List[str] = [m.get("name", "") for m in models_data]
                diag["installed_models"] = installed_names

                # Check if target model is present
                diag["model_ready"] = any(
                    target_model == name or target_model in name or name in target_model
                    for name in installed_names
                )

                # 2. Running processes check
                try:
                    res_ps = await client.get(f"{clean_url}/api/ps")
                    if res_ps.status_code == 200:
                        ps_data = res_ps.json().get("models", [])
                        diag["running_models"] = [
                            {
                                "name": p.get("name"),
                                "size_vram_mb": round(p.get("size_vram", 0) / (1024 * 1024), 2),
                                "expires_at": p.get("expires_at"),
                            }
                            for p in ps_data
                        ]
                except Exception:
                    pass

                if diag["model_ready"]:
                    diag["status"] = "ready"
                    diag["troubleshooting"] = "Local AI brain is fully operational and ready for offline inference."
                else:
                    diag["status"] = "model_missing"
                    diag["troubleshooting"] = (
                        f"Ollama is running, but model '{target_model}' is not in the local library. "
                        f"Run 'ollama pull {target_model}' in PowerShell."
                    )
            else:
                diag["status"] = "degraded"
                diag["troubleshooting"] = f"Ollama returned HTTP {res_tags.status_code}."

    except httpx.ConnectError:
        diag["status"] = "offline"
        diag["troubleshooting"] = (
            f"Cannot connect to Ollama at {clean_url}. "
            "Make sure Ollama is installed and running on your Windows PC ('ollama serve')."
        )
    except httpx.TimeoutException:
        diag["status"] = "timeout"
        diag["troubleshooting"] = (
            f"Ollama took more than 4 seconds to respond at {clean_url}. "
            "The system may be under heavy memory pressure."
        )
    except Exception as exc:
        diag["status"] = "error"
        diag["troubleshooting"] = f"Unexpected health check error: {exc}"

    return diag

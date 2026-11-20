"""
REST API endpoints for Local AI Brain Management and Storage Health.
Enables Desktop UI to monitor Ollama, switch models, run inference benchmarks,
and manage local database backups.
"""
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_role
from app.models.user import User
from app.ai.local_ai_gateway import local_ai_gateway
from app.ai.model_manager import RECOMMENDED_LOCAL_MODELS
from app.core.storage import check_storage_health, get_acttrident_data_dir

router = APIRouter()


class SwitchModelRequest(BaseModel):
    model_tag: str = Field(..., description="Target model tag (e.g. 'llama3.2:latest', 'qwen2.5:1.5b')")


class TestInferenceRequest(BaseModel):
    prompt: Optional[str] = Field("Confirm ActTrident local AI readiness.", description="Prompt to test")


@router.get("/status")
async def get_ai_status(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Retrieves real-time diagnostics on local Ollama, selected model, latency, and GPU status."""
    return await local_ai_gateway.check_health()


@router.get("/models")
async def list_available_models(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns the recommended hardware-fit catalog and currently installed local models."""
    installed = await local_ai_gateway.list_models()
    return {
        "active_model": local_ai_gateway.model_manager.active_model,
        "recommended_catalog": RECOMMENDED_LOCAL_MODELS,
        "installed_models": installed,
    }


@router.post("/switch-model")
def switch_active_model(
    req: SwitchModelRequest,
    current_user: User = Depends(require_role(["admin", "manager"])),
) -> Dict[str, Any]:
    """Switches the active local AI model for future research and outreach cycles."""
    new_model = local_ai_gateway.set_active_model(req.model_tag)
    return {
        "status": "success",
        "active_model": new_model,
        "message": f"Active local AI model switched to '{new_model}'.",
    }


@router.post("/test")
async def test_local_model_inference(
    req: TestInferenceRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Runs a live test prompt against the active local model to measure latency and output."""
    start = time.time()
    try:
        response_text = await local_ai_gateway.generate_text(
            prompt=req.prompt or "Confirm ActTrident local AI readiness.",
            system_prompt="You are ActTrident Local AI. Respond in one concise sentence.",
        )
        elapsed = round(time.time() - start, 2)
        return {
            "status": "success",
            "model": local_ai_gateway.model_manager.active_model,
            "latency_seconds": elapsed,
            "response": response_text,
            "tokens_per_second_estimate": round(len(response_text.split()) * 1.3 / max(elapsed, 0.1), 1),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Local model test failed: {exc}",
        )


@router.get("/storage")
def get_desktop_storage_status(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns local storage metrics for %LOCALAPPDATA%\\ActTrident."""
    return check_storage_health()


@router.post("/backup")
def trigger_instant_backup(
    current_user: User = Depends(require_role(["admin", "manager"])),
) -> Dict[str, Any]:
    """Creates a point-in-time SQLite backup with SHA-256 verification manifest."""
    from scripts.backup_restore_db import backup_sqlite_database, _sqlite_path_from_url
    from app.core.config import settings
    from pathlib import Path
    from datetime import datetime, timezone

    root = get_acttrident_data_dir()
    backups_dir = root / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = backups_dir / f"acttrident_backup_{timestamp}.db"

    source_db = _sqlite_path_from_url(settings.DATABASE_URL)
    manifest = backup_sqlite_database(source_db, out_file)

    return {
        "status": "success",
        "backup": manifest,
    }

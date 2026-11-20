"""
Tests for ActTrident Local AI Brain, Ollama Provider, Desktop Storage, and Local Worker.
"""
import asyncio
import pytest
from app.ai.local_ai_gateway import local_ai_gateway
from app.ai.model_manager import AIModelManager, RECOMMENDED_LOCAL_MODELS
from app.ai.prompt_manager import PromptManager
from app.ai.structured_output import ResearchDossierOutput, QualificationAIOutput, EmailDraftOutput
from app.core.storage import initialize_storage_layout, check_storage_health, get_acttrident_data_dir
from app.services.job_service import create_background_task, recover_dangling_tasks
from app.models.job import BackgroundTaskRecord


def test_model_manager_catalog():
    """Verifies that the recommended local AI model catalog includes vetted hardware-fit models."""
    manager = AIModelManager()
    catalog = manager.get_catalog()
    assert len(catalog) >= 3

    tags = [m["tag"] for m in catalog]
    assert "llama3.2:latest" in tags
    assert "qwen2.5:1.5b" in tags

    profile = manager.get_model_profile("llama3.2:latest")
    assert profile is not None
    assert profile["parameters"] == "3.2B"
    assert profile["supports_json"] is True


def test_prompt_manager_compliance_rules():
    """Verifies that PromptManager enforces zero-breach and truthfulness rules in assembled prompts."""
    pm = PromptManager()
    comp = {
        "name": "Kanchenjunga Tech",
        "city": "Gangtok",
        "industry": "Software",
        "laptop_count_verified": 16,
        "laptop_count_evidence": "16 verified ThinkPads",
    }
    sys_p, usr_p = pm.build_research_prompt(comp, "Leading software development company in Sikkim.")
    assert "NEVER allege or invent that the company suffered a cyberattack" in sys_p
    assert "Kanchenjunga Tech" in usr_p
    assert "16 verified ThinkPads" in usr_p


def test_local_ai_gateway_generation():
    """Verifies that local AI gateway generates valid structured JSON and text."""
    # 1. Text generation
    text = asyncio.run(local_ai_gateway.generate_text(
        prompt="Confirm local AI status.",
        system_prompt="Respond concisely."
    ))
    assert isinstance(text, str)
    assert len(text) > 0

    # 2. Structured JSON generation
    json_out = asyncio.run(local_ai_gateway.generate_json(
        prompt="Return test JSON object with status ok and agent ActTrident.",
        system_prompt="Respond strictly in JSON format."
    ))
    assert isinstance(json_out, dict)

    # 3. Research dossier structured output
    dossier = asyncio.run(local_ai_gateway.generate_research_dossier({
        "name": "Siliguri Cloud Networks",
        "city": "Siliguri",
        "industry": "Cloud IT",
        "laptop_count_verified": 14,
        "laptop_count_evidence": "14 Dell Latitude laptops",
    }))
    assert isinstance(dossier, ResearchDossierOutput)
    assert dossier.summary is not None
    assert dossier.relevance_score >= 0.0

    # 4. Qualification output
    qual = asyncio.run(local_ai_gateway.evaluate_qualification({
        "name": "Siliguri Cloud Networks",
        "industry": "Software",
        "laptop_count_verified": 14,
        "has_verified_5_plus_laptops": True,
    }))
    assert isinstance(qual, QualificationAIOutput)
    assert qual.score >= 0.0


def test_storage_layout_and_health():
    """Verifies %LOCALAPPDATA%\\ActTrident storage layout and integrity diagnostics."""
    dirs = initialize_storage_layout()
    assert dirs["root"].exists()
    assert dirs["data"].exists()
    assert dirs["backups"].exists()
    assert dirs["exports"].exists()

    health = check_storage_health()
    assert "status" in health
    assert "free_disk_space_gb" in health
    assert health["wal_mode_enabled"] is True


def test_local_worker_task_recovery(db_session):
    """Verifies that interrupted 'running' tasks from previous sessions are recovered safely."""
    # Create an artificial interrupted task
    stuck = BackgroundTaskRecord(
        task_id="test-stuck-uuid-1234",
        category="nightly_discovery",
        status="running",
        payload_json="{}",
    )
    db_session.add(stuck)
    db_session.commit()

    recovered_count = recover_dangling_tasks(db_session)
    assert recovered_count >= 1

    db_session.refresh(stuck)
    assert stuck.status == "pending"
    assert "Recovered automatically" in stuck.error_message


def test_local_ai_api_endpoints(client, admin_auth_headers, auth_headers):
    """Verifies REST endpoints for Local AI Brain and Desktop Storage."""
    # 1. GET /api/v1/ai/status
    res_status = client.get("/api/v1/ai/status", headers=admin_auth_headers)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["provider"] == "ollama"
    assert "endpoint" in status_data

    # 2. GET /api/v1/ai/models
    res_models = client.get("/api/v1/ai/models", headers=admin_auth_headers)
    assert res_models.status_code == 200
    models_data = res_models.json()
    assert "active_model" in models_data
    assert len(models_data["recommended_catalog"]) >= 3

    # 3. POST /api/v1/ai/test
    res_test = client.post("/api/v1/ai/test", json={"prompt": "Ping local model"}, headers=admin_auth_headers)
    assert res_test.status_code == 200
    test_data = res_test.json()
    assert test_data["status"] == "success"
    assert "latency_seconds" in test_data

    # 4. GET /api/v1/ai/storage
    res_storage = client.get("/api/v1/ai/storage", headers=admin_auth_headers)
    assert res_storage.status_code == 200
    storage_data = res_storage.json()
    assert "database_file" in storage_data
    assert "free_disk_space_gb" in storage_data

    # 5. POST /api/v1/ai/switch-model RBAC: sales_rep blocked with 403
    res_switch_rep = client.post("/api/v1/ai/switch-model", json={"model_tag": "qwen2.5:1.5b"}, headers=auth_headers)
    assert res_switch_rep.status_code == 403

    # 6. POST /api/v1/ai/switch-model allowed for admin
    res_switch_admin = client.post("/api/v1/ai/switch-model", json={"model_tag": "llama3.2:latest"}, headers=admin_auth_headers)
    assert res_switch_admin.status_code == 200
    assert res_switch_admin.json()["active_model"] == "llama3.2:latest"

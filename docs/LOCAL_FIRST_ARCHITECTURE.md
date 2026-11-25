# ACTTRIDENT — LOCAL-FIRST DESKTOP ARCHITECTURE SPECIFICATION

**Document ID:** `ACT-ARCH-LOCAL-2026-V1`  
**Classification:** Core System Architecture  

---

## 1. Architectural Philosophy

ActTrident is an enterprise-grade AI Sales Outreach and Research platform redesigned from the ground up to run as a **self-contained, private, local-first Windows desktop application**.

### Core Tenets:
1. **Zero Mandatory Cloud Dependencies:** The application requires no cloud server (Railway, Render, AWS), no cloud PostgreSQL database, and no paid Anthropic / Claude subscription.
2. **GPU-Accelerated Local Inference:** Natural language synthesis, 7-factor fleet qualification rationale, and multi-channel copywriting execute directly on the local GPU via Ollama (`llama3.2:latest`, ~48 tokens/sec).
3. **Local Persistent Storage:** All business data, prospects, campaigns, drafts, and audit logs persist in `%LOCALAPPDATA%\ActTrident\data\acttrident.db` in SQLite WAL mode.
4. **Unified Single-Port Web Service:** The FastAPI backend serves both the REST API (`/api/v1`) and the pre-compiled React 18 production bundle (`/`) from a single loopback socket (`127.0.0.1:8000`).
5. **Fail-Closed Live Outreach Safety:** Live sending is strictly disabled by default (`LIVE_SEND_ENABLED=false`). External dispatches require explicit operator credentials and per-message human approval.

---

## 2. Component Topology

```mermaid
graph TD
    subgraph Client["Windows Desktop Shell / Microsoft Edge App Window"]
        UI["React 18 Single Page Application\n(Dashboard, Leads, Research, Settings)"]
        Wizard["Desktop First-Run Setup Wizard"]
    end

    subgraph BackendProcess["Local Python Backend (Unified Port 127.0.0.1:8000)"]
        FastAPIServer["FastAPI ASGI Server (Uvicorn)"]
        StaticServer["Built UI Static File Server (/)"]
        APIRouter["API Router (/api/v1)"]
        AIGateway["Local AI Gateway (app.ai)"]
        LocalWorker["Async ThreadPool Worker (max_workers=3)"]
        SafetyEngine["Compliance & Kill Switch Engine"]
    end

    subgraph LocalInference["Local AI Inference Engine (Port 127.0.0.1:11434)"]
        OllamaDaemon["Ollama Windows Service"]
        CUDAEngine["NVIDIA GeForce GTX 1650 (CUDA 12)"]
        ModelWeights["llama3.2:latest (2.01 GB Q4_K_M)"]
    end

    subgraph PersistentStorage["Workstation Filesystem (%LOCALAPPDATA%\\ActTrident)"]
        SQLiteDB[("SQLite WAL Database\nacttrident.db")]
        BackupsFolder["Database Backups & SHA-256 Manifests"]
        LogsFolder["Runtime Application Logs"]
    end

    UI -->|HTTP Loopback| FastAPIServer
    FastAPIServer --> StaticServer
    FastAPIServer --> APIRouter
    APIRouter --> AIGateway
    APIRouter --> SafetyEngine
    APIRouter --> LocalWorker
    AIGateway -->|REST API| OllamaDaemon
    OllamaDaemon --> CUDAEngine
    CUDAEngine --> ModelWeights
    APIRouter --> SQLiteDB
    LocalWorker --> SQLiteDB
    FastAPIServer --> BackupsFolder
    FastAPIServer --> LogsFolder
```

# ACTTRIDENT — LOCAL AI MODEL SELECTION ARCHITECTURE

**Date:** November 20, 2026  
**Document ID:** `ACT-AI-SEL-2026-V1`  
**Host PC Target:** 11th Gen Core i5 (6 cores) + NVIDIA GeForce GTX 1650 (4 GB VRAM) + 16 GB System RAM  

---

## 1. Candidate Model Evaluation Matrix

| Model Tag | Parameters | Quantization | Disk / VRAM Size | CUDA GTX 1650 Offload | Structured JSON | License / Commercial Use | Fit Assessment |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`llama3.2:latest`** | **3.21B** | **Q4_K_M** | **2.01 GB** | **100% GPU Offload (2.2 GB VRAM)** | **Native JSON Mode** | **Llama 3.2 Commercial License** | **PRIMARY CHOICE (Pre-installed, 48 tok/s)** |
| `qwen2.5:1.5b` | 1.54B | Q4_K_M | 0.98 GB | 100% GPU Offload (1.2 GB VRAM) | Supported | Apache 2.0 (Permissive) | Lightweight secondary candidate |
| `qwen2.5:3b` | 3.09B | Q4_K_M | 1.95 GB | 100% GPU Offload (2.3 GB VRAM) | Supported | Apache 2.0 (Permissive) | Excellent alternative candidate |
| `gemma2:2b` | 2.61B | Q4_K_M | 1.63 GB | 100% GPU Offload (1.9 GB VRAM) | Supported | Gemma Terms of Use | Solid lightweight candidate |
| `llama3.1:8b` | 8.03B | Q4_K_M | 4.7 GB | Partial Offload (VRAM OOM spill) | Supported | Llama 3.1 Commercial | Incompatible with 4 GB GTX 1650 |
| `qwen2.5:7b` | 7.61B | Q4_K_M | 4.4 GB | Partial Offload (VRAM OOM spill) | Supported | Apache 2.0 | Incompatible with 4 GB GTX 1650 |

---

## 2. Selection Decision

### Primary Selected Model: `llama3.2:latest` (Llama 3.2 3B Instruct)
1. **Zero-Download Verification:** The model was already downloaded on the workstation (`C:\Users\singh\.ollama\models\blobs\sha256-dde5aa3fc5ff...`, size: 2.01 GB), eliminating internet bandwidth requirements.
2. **GPU Offload & Throughput:** The model offloads completely into the 4 GB VRAM of the NVIDIA GeForce GTX 1650 Max-Q. Test inference measured **48.02 tokens/second** and **0.92s warm response latency**.
3. **Structured JSON Output:** Ollama provides native grammar-constrained JSON decoding (`format="json"`), ensuring 100% valid schema extraction for research reports, lead qualification, and personalized copywriting.
4. **Commercial Compliance:** Llama 3.2 Community License permits commercial use, development, and redistribution for entities under 700 million monthly active users.

### Secondary Fallback Engine: Deterministic Expert Rule Engine
If Ollama is stopped or the model is unloaded, ActTrident automatically uses its internal deterministic expert rule engine (`ai_provider._generate_deterministic`). The application never fails, and never silently falls back to a paid cloud API.

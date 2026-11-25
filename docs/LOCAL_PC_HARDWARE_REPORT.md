# ACTTRIDENT — LOCAL PC HARDWARE SPECIFICATIONS & AUDIT REPORT

**Date of Audit:** November 20, 2026  
**Auditor:** Principal Software Architect & Windows Desktop Engineer  
**Host Machine:** Singh Workstation (Local Windows Desktop)  
**Execution Environment:** Native Windows 11 (64-bit)  

---

## 1. System Specifications (Physical Audit)

| Component | Hardware Metric / Specification | Status / Suitability |
| :--- | :--- | :--- |
| **Operating System** | Microsoft Windows 11 Home Single Language (Build 10.0.26300, 64-bit) | Fully Compatible |
| **Processor (CPU)** | 11th Gen Intel(R) Core(TM) i5-11400H @ 2.70 GHz (6 Cores, 12 Logical Processors) | Supported (AVX2 enabled) |
| **Total System RAM** | **15.71 GB** Physical DDR4 | Sufficient for 1.5B–4B local models |
| **Available RAM** | **1.42 GB** available at idle/background load | Moderate memory pressure; small models required |
| **Primary GPU** | **NVIDIA GeForce GTX 1650 with Max-Q Design** (Driver: 32.0.16.1078) | CUDA 12+ Acceleration Active |
| **Dedicated VRAM** | **4.0 GB GDDR6** | Sufficient to offload <= 3.5B models completely |
| **Integrated GPU** | Intel(R) UHD Graphics (Driver: 32.0.101.7088, 2 GB shared) | Secondary Display Device |
| **Drive C: Storage** | **14.34 GB Free** / 258.32 GB (NVMe SSD) | Tight space; recommended for core app only |
| **Drive D: Storage** | **162.49 GB Free** / 195.31 GB (Storage SSD/HDD) | **Optimal location for additional Ollama models** |
| **Python Runtime** | Python 3.14.5 (64-bit) | Native Windows installation |
| **Node.js & npm** | Node.js v24.16.0, npm 11.13.0 | Compatible with Vite & React frontend |

---

## 2. Ollama & Local AI Environment Audit

| Component | Detected State | Status |
| :--- | :--- | :--- |
| **Ollama Executable** | `C:\Users\singh\AppData\Local\Programs\Ollama\ollama.exe` | **Installed (v0.34.4)** |
| **Ollama Daemon Status** | Running locally on `127.0.0.1:11434` with CUDA acceleration | **Active & Responding** |
| **Pre-Installed Models** | `llama3.2:latest` (`a80c4f17acd5`, size **2.01 GB**) | **Verified & Ready** |
| **Model Weight Location** | `C:\Users\singh\.ollama\models\blobs\` | Present on disk |
| **Inference Hardware** | CUDA 0 offload (NVIDIA GeForce GTX 1650) + Flash Attention | **48.02 tokens/sec observed** |
| **Warm Response Latency** | **0.92 seconds** total response time | Excellent interactive speed |

---

## 3. Hardware Constraints & Operational Policy

1. **VRAM Limit (4 GB):** The NVIDIA GeForce GTX 1650 has 4,096 MB VRAM. A 3B quantized model (`llama3.2:3b` at Q4_K_M) requires ~2.0 GB for model weights and ~450 MB for KV cache (context window 4096), leaving ~1.5 GB VRAM headroom for the display driver and desktop compositor.
2. **System RAM Pressure:** Current free RAM is ~1.4 GB. Models exceeding 7B would spill into system RAM and cause Windows pagefile thrashing. Models must be capped at 3B–4B for optimal zero-lag execution.
3. **Storage Allocation:** Drive C: has 14.34 GB free space. The pre-installed `llama3.2:latest` model uses 2.01 GB. If secondary models (such as `qwen2.5:1.5b` or `gemma2:2b`) are installed, configure `$env:OLLAMA_MODELS = "D:\OllamaModels"` to leverage the 162.49 GB free space on Drive D:.

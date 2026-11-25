# ACTTRIDENT — LOCAL AI & OLLAMA TROUBLESHOOTING RUNBOOK

**Target Diagnostics:** Windows Workstation with Ollama v0.34.4  

---

## 1. Issue: Ollama Not Responding on 127.0.0.1:11434

### Symptoms:
- Settings View shows **OLLAMA OFFLINE (Rule Engine Active)**.
- First-Run Wizard warns that Ollama is unreachable.

### Remediation:
1. Open PowerShell and start Ollama manually:
   ```powershell
   ollama serve
   ```
2. Check if another process is occupying port 11434:
   ```powershell
   Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
   ```
3. Test connectivity:
   ```powershell
   Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags"
   ```

---

## 2. Issue: Model Loading Timeout on First Inference

### Symptoms:
- The first AI inference request takes 35-45 seconds to respond.

### Explanation:
On cold startup, Ollama must load model weights (2.01 GB) from disk into GPU VRAM and perform a CUDA warmup pass. Once warm, subsequent requests execute in under 1 second (~48 tokens/sec).

### Optimization:
- In `backend/app/core/config.py`, `OLLAMA_TIMEOUT_SECONDS` is set to `60` seconds to accommodate cold load times.
- Keep Ollama running in the background to preserve warm memory state.

---

## 3. Issue: Selected Model Not in Local Library

### Symptoms:
- API returns `Model 'llama3.2:latest' not found in local Ollama library`.

### Remediation:
Pull the model from official Ollama repository:
```powershell
ollama pull llama3.2:latest
```

---

## 4. Issue: Low Disk Space on Drive C:

### Symptoms:
- Disk warning during model download.

### Remediation:
Move model storage to Drive D: where 160+ GB free space is available:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\OllamaModels", "User")
New-Item -ItemType Directory -Path "D:\OllamaModels" -Force
Stop-Process -Name "ollama*" -Force
ollama serve
```

---

## 5. Automatic Safe Degradation

If Ollama cannot be started, ActTrident automatically activates its **Deterministic Expert Fallback Engine**. The application remains 100% operational, processes lead qualification, and generates standard compliant outreach drafts without failing or contacting paid cloud services.

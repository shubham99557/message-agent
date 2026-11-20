# ACTTRIDENT — OLLAMA INSTALLATION & LOCAL AI SETUP GUIDE

**Target System:** Windows 10 / Windows 11 (64-bit)  
**Supported AI Engine:** Ollama for Windows (Official)  
**Default Model:** `llama3.2:latest` (Llama 3.2 3B Instruct)  

---

## 1. Quick Verification (Ollama Already Installed)

If you already have Ollama installed, verify that the service is running and listening:

```powershell
# Check Ollama version
ollama --version

# List installed models
ollama list

# Test API connectivity
Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags"
```

---

## 2. Fresh Installation (If Missing)

1. Download the official installer:  
   [https://ollama.com/download/windows](https://ollama.com/download/windows)
2. Run `OllamaSetup.exe` (installs per-user to `%LOCALAPPDATA%\Programs\Ollama\`).
3. Complete the standard installer prompts.
4. Verify from PowerShell:
   ```powershell
   ollama --version
   ```

---

## 3. Recommended Models for ActTrident

ActTrident is optimized for lightweight, high-throughput quantized instruction models:

| Model | Size | Pull Command | Recommendation |
| :--- | :---: | :--- | :--- |
| **`llama3.2:latest`** | **2.01 GB** | `ollama pull llama3.2:latest` | **Primary Choice (Pre-installed, 48 tok/s on GTX 1650)** |
| `qwen2.5:1.5b` | 0.98 GB | `ollama pull qwen2.5:1.5b` | Ultra-lightweight fallback for low memory |
| `qwen2.5:3b` | 1.95 GB | `ollama pull qwen2.5:3b` | High-accuracy multilingual research |
| `gemma2:2b` | 1.63 GB | `ollama pull gemma2:2b` | Fast Google-designed compact model |

---

## 4. Storing Models on a Secondary Drive (e.g. Drive D:)

If Drive C: is low on disk space, you can redirect model downloads to Drive D: where more space is available:

```powershell
# Set OLLAMA_MODELS environment variable permanently
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\OllamaModels", "User")

# Create target directory
New-Item -ItemType Directory -Path "D:\OllamaModels" -Force

# Restart Ollama service
Stop-Process -Name "ollama*" -Force -ErrorAction SilentlyContinue
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve"
```

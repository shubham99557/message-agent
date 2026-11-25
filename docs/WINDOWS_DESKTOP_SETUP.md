# ACTTRIDENT — WINDOWS DESKTOP SETUP & LAUNCH GUIDE

**Platform:** Windows 10 & 11 (64-bit)  
**Product:** ActTrident Local-First AI Sales Agent  

---

## 1. Quick Launch Options

ActTrident offers three launch mechanisms on Windows:

### Option A: Desktop Shortcut (Recommended)
Double-click the **`ActTrident AI Sales Agent`** shortcut on your Windows Desktop.

### Option B: Windows Start Menu
Open the Windows Start Menu, navigate to **Programs ➔ ActTrident**, and click **`ActTrident AI Sales Agent`**.

### Option C: Command Line Launcher
From PowerShell or Command Prompt in the repository folder:
```powershell
.\scripts\start_acttrident_desktop.bat
```

---

## 2. What Happens When You Launch ActTrident

1. **Hardware & Ollama Verification:** Checks whether Ollama is active on `127.0.0.1:11434`. If stopped, it automatically starts `ollama serve`.
2. **Unified Backend Activation:** Starts the ActTrident FastAPI server on `127.0.0.1:8000`, serving both API endpoints and the built frontend application.
3. **Storage & Task Recovery:** Verifies the database in `%LOCALAPPDATA%\ActTrident\data\acttrident.db` and recovers any tasks interrupted during previous sessions.
4. **App Window Launch:** Automatically opens Microsoft Edge in standalone Application Mode (`msedge --app=http://127.0.0.1:8000/`) or your default browser.

---

## 3. Stopping ActTrident

To shut down the application cleanly:
```powershell
.\scripts\stop_acttrident_desktop.bat
```
This terminates the background server process on port 8000 without closing or disrupting unrelated Ollama instances or user applications.

---

## 4. Re-Creating Desktop Shortcuts

If you move the project folder or wish to regenerate desktop shortcuts:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/create_windows_shortcuts.ps1
```

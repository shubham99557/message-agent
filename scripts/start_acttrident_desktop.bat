@echo off
title ActTrident AI Sales Agent - Local Desktop
echo ============================================================
echo   ActTrident AI Outreach & Sales Agent - Local Desktop
echo   Local-First AI Brain (Ollama) + Persistent Storage
echo ============================================================
echo.

:: 1. Set Local-First Environment Variables
set AI_PROVIDER=ollama
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=llama3.2:latest
set LIVE_SEND_ENABLED=false
set USE_LOCAL_WORKER=true
set ENVIRONMENT=development
set LOCAL_APP_DATA_DIR=%LOCALAPPDATA%\ActTrident

:: Ensure logs directory exists
if not exist "%LOCALAPPDATA%\ActTrident\logs" mkdir "%LOCALAPPDATA%\ActTrident\logs"

:: 2. Check if Ollama is running on 127.0.0.1:11434
echo [1/4] Checking Local AI Brain (Ollama)...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1; exit 0 } catch { exit 1 }" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] Ollama is active on 127.0.0.1:11434.
) else (
    echo   [INFO] Starting local Ollama server daemon...
    start /B "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve >nul 2>&1
    timeout /t 3 /nobreak >nul
)

:: 3. Check if ActTrident is ALREADY running and healthy
echo [2/4] Verifying Application Server State...
powershell -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 1; if ($r.status -eq 'ready') { exit 0 } } catch {}; exit 1" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [OK] ActTrident Server is already running and ready on 127.0.0.1:8000.
    goto launch_ui
)

:: If port 8000 is occupied but not ready, terminate the stale process
powershell -Command "
$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -like '*python*') {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
" >nul 2>&1

:: Start Unified ActTrident Application Server (Port 8000)
echo [2/4] Starting ActTrident Desktop Backend (127.0.0.1:8000)...
cd /d "%~dp0\..\backend"
start /B "" python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "%LOCALAPPDATA%\ActTrident\logs\acttrident_server.log" 2>&1

:: 4. Wait for server readiness
echo [3/4] Waiting for application initialization...
powershell -Command "for ($i=0; $i -lt 30; $i++) { try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 1; if ($r.status -eq 'ready') { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARNING] Server took longer than expected to initialize. Opening browser anyway...
) else (
    echo   [OK] Application server is healthy and ready.
)

:launch_ui
:: 5. Launch User Interface
echo [4/4] Launching ActTrident Desktop Window...
where msedge >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" msedge --app=http://127.0.0.1:8000/
) else (
    start "" "http://127.0.0.1:8000/"
)

echo.
echo ============================================================
echo   ActTrident is now running at: http://127.0.0.1:8000
echo   To stop the application, run scripts\stop_acttrident_desktop.bat
echo ============================================================
echo.

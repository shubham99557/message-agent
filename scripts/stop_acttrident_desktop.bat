@echo off
title Stop ActTrident Desktop
echo Stopping ActTrident Application Server (Port 8000)...

powershell -Command "
$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conns) {
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($p -and $p.ProcessName -like '*python*') {
            Write-Host ('Stopping ActTrident backend PID: ' + $p.Id)
            Stop-Process -Id $p.Id -Force
        }
    }
    Write-Host 'ActTrident application stopped successfully.'
} else {
    Write-Host 'ActTrident is not currently running on port 8000.'
}
"
echo Done.

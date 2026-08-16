# Verifica el entorno antes de instalar WSL Manager
# Uso: powershell -ExecutionPolicy Bypass -File scripts\check_environment.ps1

Write-Host "== Check de entorno WSL Manager ==" -ForegroundColor Cyan

# 1. Python
try {
    $py = (Get-Command python -ErrorAction Stop).Source
    Write-Host "[OK] python: $py"
    python --version
} catch {
    Write-Host "[FAIL] python no encontrado" -ForegroundColor Red
}

# 2. WSL
try {
    wsl --version | Out-Null
    Write-Host "[OK] wsl.exe disponible"
    wsl -l -v
} catch {
    Write-Host "[FAIL] wsl.exe no disponible o WSL sin inicializar" -ForegroundColor Red
    Write-Host "       Ejecuta: wsl --install -d Ubuntu"
}

# 3. Permisos de escritura de %APPDATA%
$cfg = Join-Path $env:APPDATA "WSLManager"
try {
    New-Item -ItemType Directory -Path $cfg -Force | Out-Null
    Write-Host "[OK] %APPDATA%\WSLManager creado: $cfg"
} catch {
    Write-Host "[FAIL] no se pudo crear %APPDATA%\WSLManager" -ForegroundColor Red
}

# 4. SQLite3 (viene con Python)
try {
    python -c "import sqlite3; print('[OK] sqlite3', sqlite3.sqlite_version)"
} catch {
    Write-Host "[FAIL] sqlite3 no disponible" -ForegroundColor Red
}

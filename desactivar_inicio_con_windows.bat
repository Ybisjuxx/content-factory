@echo off
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
if exist "%STARTUP_DIR%\Content Factory AutoStart.lnk" (
    del "%STARTUP_DIR%\Content Factory AutoStart.lnk"
    echo [OK] Inicio automatico con Windows desactivado.
) else (
    echo [INFO] No habia inicio automatico configurado.
)
timeout /t 3 > nul

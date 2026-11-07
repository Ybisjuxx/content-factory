@echo off
title Content Factory - 100%% Local Video Factory
cd /d "%~dp0"
set PYTHONPATH=.

echo ===================================================
echo     Iniciando Content Factory (100%% Local)
echo ===================================================
echo Servidor en: http://127.0.0.1:8000
echo Abriendo navegador en http://127.0.0.1:8000 ...

start http://127.0.0.1:8000

python -m app.cli serve --host 127.0.0.1 --port 8000
pause

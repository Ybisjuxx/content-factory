@echo off
title Content Factory - Servidor Activo (127.0.0.1:8000)
color 0B
cd /d "C:\Developer\content_factory"

echo =======================================================
echo         CONTENT FACTORY - 100%% LOCAL AI SUITE
echo =======================================================
echo.
echo Servidor activo en: http://127.0.0.1:8000
echo Abriendo tablero en tu navegador...
echo (Puedes minimizar esta ventana, mantendra el servidor activo)
echo.

start http://127.0.0.1:8000

"C:\Users\ybis\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause

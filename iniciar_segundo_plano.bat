@echo off
cd /d "C:\Developer\content_factory"
set PYTHONPATH=C:\Developer\content_factory

:: Verificar si el servidor ya esta activo en el puerto 8000
netstat -ano | findstr :8000 | findstr LISTENING > nul
if %errorlevel% neq 0 (
    start /b "" python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > "storage\server.log" 2>&1
    ping 127.0.0.1 -n 3 > nul
)

:: Abrir navegador en el dashboard
start http://127.0.0.1:8000
exit

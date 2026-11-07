@echo off
echo Buscando proceso de Content Factory en el puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Deteniendo PID %%a...
    taskkill /F /PID %%a
)
echo Servidor detenido.
timeout /t 2 /nobreak > nul
exit

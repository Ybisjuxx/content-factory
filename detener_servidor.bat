@echo off
echo Buscando proceso de Content Factory en el puerto 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Deteniendo PID %%a...
    taskkill /F /PID %%a > nul 2>&1
)
echo Servidor detenido.
ping 127.0.0.1 -n 2 > nul
exit

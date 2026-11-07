@echo off
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $shortcut = $WshShell.CreateShortcut('%STARTUP_DIR%\Content Factory AutoStart.lnk'); $shortcut.TargetPath = 'wscript.exe'; $shortcut.Arguments = '\"C:\Developer\content_factory\launch_silent.vbs\"'; $shortcut.WorkingDirectory = 'C:\Developer\content_factory'; $shortcut.Save()"
echo.
echo [OK] Content Factory ahora iniciara silenciosamente en segundo plano cada vez que enciendas tu PC.
echo Podras abrir http://127.0.0.1:8000 directamente en cualquier navegador.
timeout /t 3 > nul

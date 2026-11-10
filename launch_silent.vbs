Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Developer\content_factory"
WshShell.Run """C:\Users\ybis\AppData\Local\Programs\Python\Python312\pythonw.exe"" ""C:\Developer\content_factory\run_server.py""", 0, False

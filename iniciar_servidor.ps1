param(
    [switch]$NoBrowser
)

Set-Location -Path "C:\Developer\content_factory"
$env:PYTHONPATH = "C:\Developer\content_factory"

$pythonCandidates = @(
    "C:\Users\ybis\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Users\ybis\AppData\Local\Programs\Python\Python312\pythonw.exe",
    "python"
)

$pythonExe = $null
foreach ($cand in $pythonCandidates) {
    if (Test-Path $cand) {
        $pythonExe = $cand
        break
    }
}
if (-not $pythonExe) {
    $pythonExe = "python"
}

$port = 8000
$serverUrl = "http://127.0.0.1:$port"

# Check if port 8000 is already listening
$conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if (-not $conn) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pythonExe
    $psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port $port"
    $psi.WorkingDirectory = "C:\Developer\content_factory"
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $true
    [System.Diagnostics.Process]::Start($psi) | Out-Null
}

# Wait until server is responding (up to 15s)
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = Invoke-WebRequest -Uri "$serverUrl/api/v1/system/health" -UseBasicParsing -TimeoutSec 1
        if ($res.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
    Start-Sleep -Milliseconds 500
}

# Open browser if requested
if (-not $NoBrowser) {
    Start-Process $serverUrl
}

exit 0


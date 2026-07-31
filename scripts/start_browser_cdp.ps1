param(
    [int]$Port = 9223,
    [string]$ProfilePath = "$env:TEMP\papersage-browser-cdp"
)

$chromePath = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path -LiteralPath $chromePath)) {
    throw "Chrome was not found at $chromePath"
}

try {
    Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 1 | Out-Null
    Write-Output "Chrome CDP is already available on port $Port."
    exit 0
} catch {
    # No existing CDP browser is listening on the requested port.
}

New-Item -ItemType Directory -Force -Path $ProfilePath | Out-Null
$arguments = @(
    "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfilePath",
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank"
)
Start-Process -FilePath $chromePath -ArgumentList $arguments -WindowStyle Hidden

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 1 | Out-Null
        Write-Output "Chrome CDP is ready on port $Port."
        exit 0
    } catch {
        # Chrome has not exposed CDP yet.
    }
}

throw "Chrome did not expose CDP on port $Port."

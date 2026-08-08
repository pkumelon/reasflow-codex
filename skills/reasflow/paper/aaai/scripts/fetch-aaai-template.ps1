param(
    [string]$Dest = "templates/aaai"
)
$ErrorActionPreference = "Stop"

$url = "https://aaai.org/authorkit26-1/"
$guidelinesUrl = "https://aaai.org/conference/aaai/aaai-26/main-technical-track-call/"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

$curl = if (Get-Command curl.exe -ErrorAction SilentlyContinue) { "curl.exe" }
        elseif (Get-Command curl -ErrorAction SilentlyContinue) { "curl" }
        else { throw "curl (or curl.exe) is required" }

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("aaai-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = Join-Path $tmp "aaai.zip"

try {
    & $curl -fsSL -A $ua $url -o $zip
    if ($LASTEXITCODE -ne 0) { throw "failed to download: $url" }
    $bytes = [System.IO.File]::ReadAllBytes($zip)
    if (-not ($bytes[0] -eq 0x50 -and $bytes[1] -eq 0x4B)) {
        throw "unexpected response from AAAI (likely a Cloudflare challenge page). Retry or download the Author Kit manually from: $guidelinesUrl"
    }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $src = Get-ChildItem -Path $tmp -Recurse -Directory | Where-Object { $_.FullName -match "CameraReady[\\/]LaTeX$" } | Select-Object -First 1
    if (-not $src) { throw "unexpected Author Kit layout" }
    foreach ($name in @("aaai2026.sty", "aaai2026.bst", "aaai2026.bib")) {
        Copy-Item (Join-Path $src.FullName $name) (Join-Path $Dest $name) -Force
    }
    Write-Host "AAAI template ready: $Dest"
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

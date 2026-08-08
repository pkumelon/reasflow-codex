param(
    [string]$Dest = "templates/csiam"
)
$ErrorActionPreference = "Stop"

$csiamClsUrl = "https://admin.global-sci.org/uploads/ueditor/file/20240614/1718345545407042.cls"
$csiamTexUrl = "https://admin.global-sci.org/uploads/ueditor/file/20240513/1715569785769430.tex"
$algorithmicxUrls = @(
    "https://mirrors.tuna.tsinghua.edu.cn/CTAN/macros/latex/contrib/algorithmicx.zip",
    "https://mirror.easyname.at/ctan/macros/latex/contrib/algorithmicx.zip"
)
$guidelinesUrl = "https://journal.hep.com.cn/csiam-am/EN/guidelines"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

$curl = if (Get-Command curl.exe -ErrorAction SilentlyContinue) { "curl.exe" }
        elseif (Get-Command curl -ErrorAction SilentlyContinue) { "curl" }
        else { throw "curl (or curl.exe) is required" }

function Invoke-Curl([string]$Url, [string]$OutFile) {
    & $curl -fsSL -A $ua $Url -o $OutFile 2>$null
    return $LASTEXITCODE -eq 0
}

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("algorithmicx-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

try {
    if (-not (Invoke-Curl $csiamClsUrl (Join-Path $Dest "csiam-am.cls"))) { throw "failed to download: $csiamClsUrl" }
    if (-not (Invoke-Curl $csiamTexUrl (Join-Path $Dest "csiam-am-template.tex"))) { throw "failed to download: $csiamTexUrl" }
    $zip = Join-Path $tmp "algorithmicx.zip"
    $ok = $false
    foreach ($u in $algorithmicxUrls) {
        if (Invoke-Curl $u $zip) { $ok = $true; break }
    }
    if (-not $ok) { throw "failed to download algorithmicx (CTAN)" }
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    foreach ($name in @("algcompatible.sty", "algorithmicx.sty", "algpseudocode.sty")) {
        Copy-Item (Join-Path (Join-Path $tmp "algorithmicx") $name) (Join-Path $Dest $name) -Force
    }
    Write-Host "CSIAM template ready: $Dest"
}
catch {
    Write-Error "download failed: $($_.Exception.Message)"
    Write-Host "CSIAM class and template are also available from: $guidelinesUrl"
    exit 1
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

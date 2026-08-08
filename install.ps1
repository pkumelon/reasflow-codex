param(
    [switch]$Global,
    [switch]$Dev,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repo = if ($env:REASFLOW_DEV_REPO) { $env:REASFLOW_DEV_REPO } else { "pkumelon/reasflow-codex" }
$ref = if ($env:REASFLOW_DEV_REF) { $env:REASFLOW_DEV_REF } else { "main" }
$sourceOverride = $env:REASFLOW_DEV_SOURCE_DIR

function Get-UserHomeDir {
    if ($env:USERPROFILE) { return $env:USERPROFILE }

    $homeFromDotNet = [Environment]::GetFolderPath("UserProfile")
    if ($homeFromDotNet) { return $homeFromDotNet }

    if ($HOME) { return $HOME }

    throw "cannot determine user home directory"
}

if ($Global) {
    $homeDir = Get-UserHomeDir
    $targetRoot = $homeDir
    $defaultStateDir = Join-Path $homeDir ".reasflow-dev"
    $stateDir = if ($env:REASFLOW_DEV_STATE_DIR) { $env:REASFLOW_DEV_STATE_DIR } else { $defaultStateDir }
} else {
    $targetRoot = (Get-Location).Path
    $stateDir = if ($env:REASFLOW_DEV_STATE_DIR) { $env:REASFLOW_DEV_STATE_DIR } else { Join-Path $targetRoot ".reasflow-dev" }
}

$agentsDir = Join-Path $targetRoot ".codex/agents"
$skillsDir = Join-Path $targetRoot ".agents/skills"
$privateSkillsDir = Join-Path $targetRoot ".codex/reasflow-skills"
$manifest = Join-Path $stateDir "manifest.txt"
$tmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("reasflow-codex-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

try {
    New-Item -ItemType Directory -Force -Path $agentsDir, $skillsDir, $privateSkillsDir, $stateDir | Out-Null

    if (Test-Path $manifest) {
        foreach ($line in Get-Content $manifest) {
            if ($line.StartsWith("FILE ")) {
                $path = $line.Substring(5)
                if (Test-Path $path) {
                    Remove-Item -Recurse -Force $path
                }
            }
        }
    }

    if ($sourceOverride) {
        $sourceDir = (Resolve-Path $sourceOverride).Path
    } elseif ($Dev) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw "git is required for --Dev"
        }
        $sourceDir = Join-Path $stateDir "source"
        if (-not (Test-Path (Join-Path $sourceDir ".git"))) {
            git clone "https://github.com/$repo.git" $sourceDir | Out-Null
        }
        git -C $sourceDir fetch --tags origin | Out-Null
        git -C $sourceDir checkout $ref | Out-Null
        try {
            git -C $sourceDir pull --ff-only origin $ref | Out-Null
        } catch {
        }
    } else {
        $zipPath = Join-Path $tmpDir "reasflow-codex.zip"
        Invoke-WebRequest -Uri "https://codeload.github.com/$repo/zip/$ref" -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $tmpDir -Force
        $sourceDir = (Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1).FullName
    }

    if (-not (Test-Path (Join-Path $sourceDir "skills"))) { throw "invalid source: missing skills directory" }
    if (-not (Test-Path (Join-Path $sourceDir "agents"))) { throw "invalid source: missing agents directory" }

    $manifestLines = @(
        "MODE " + $(if ($Dev) { "dev" } else { "release" }),
        "SCOPE " + $(if ($Global) { "global" } else { "local" }),
        "SOURCE $sourceDir"
    )

    $sharedRoot = Join-Path $sourceDir "skills/reasflow/shared"
    if (Test-Path $sharedRoot) {
        foreach ($skill in Get-ChildItem -Path $sharedRoot -Directory) {
            $dest = Join-Path $skillsDir $skill.Name
            if ((Test-Path $dest) -and -not $Force) { throw "target already exists: $dest" }
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            if ($Dev) {
                New-Item -ItemType SymbolicLink -Path $dest -Target $skill.FullName | Out-Null
            } else {
                Copy-Item -Recurse -Force $skill.FullName $dest
            }
            $manifestLines += "FILE $dest"
        }
    }

    foreach ($category in Get-ChildItem -Path (Join-Path $sourceDir "skills/reasflow") -Directory) {
        if ($category.Name -eq "shared") { continue }
        $categoryDest = Join-Path $privateSkillsDir $category.Name
        New-Item -ItemType Directory -Force -Path $categoryDest | Out-Null
        foreach ($skill in Get-ChildItem -Path $category.FullName -Directory) {
            $dest = Join-Path $categoryDest $skill.Name
            if ((Test-Path $dest) -and -not $Force) { throw "target already exists: $dest" }
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            if ($Dev) {
                New-Item -ItemType SymbolicLink -Path $dest -Target $skill.FullName | Out-Null
            } else {
                Copy-Item -Recurse -Force $skill.FullName $dest
            }
            $manifestLines += "FILE $dest"
        }
    }

    foreach ($agent in Get-ChildItem -Path (Join-Path $sourceDir "agents") -Filter *.toml -File) {
        $dest = Join-Path $agentsDir $agent.Name
        if ((Test-Path $dest) -and -not $Force) { throw "target already exists: $dest" }
        if (Test-Path $dest) { Remove-Item -Force $dest }
        if ($Dev) {
            New-Item -ItemType SymbolicLink -Path $dest -Target $agent.FullName | Out-Null
        } else {
            Copy-Item -Force $agent.FullName $dest
        }
        $manifestLines += "FILE $dest"
    }

    # Install project-level Codex config (orchestrator developer_instructions).
    # Local install only: a global install would write into the user's personal
    # ~/.codex/config.toml and clobber their model/provider/projects settings.
    $configSrc = Join-Path $sourceDir "codex-config.toml"
    $configInstalled = $false
    if (-not $Global -and (Test-Path $configSrc)) {
        $configDest = Join-Path $targetRoot ".codex/config.toml"
        if ((Test-Path $configDest) -and -not $Force) { throw "target already exists: $configDest" }
        if (Test-Path $configDest) { Remove-Item -Force $configDest }
        if ($Dev) {
            New-Item -ItemType SymbolicLink -Path $configDest -Target $configSrc | Out-Null
        } else {
            Copy-Item -Force $configSrc $configDest
        }
        $manifestLines += "FILE $configDest"
        $configInstalled = $true
    } elseif ($Global) {
        Write-Host "  note: skipping .codex/config.toml on global install (install locally per project)"
    }

    Set-Content -Path $manifest -Value $manifestLines

    $sharedSkillCount = (Get-ChildItem -Path $skillsDir -Directory).Count
    $privateSkillCount = (Get-ChildItem -Path $privateSkillsDir -Directory | ForEach-Object { (Get-ChildItem -Path $_.FullName -Directory).Count } | Measure-Object -Sum).Sum
    if ($null -eq $privateSkillCount) { $privateSkillCount = 0 }
    $agentCount = (Get-ChildItem -Path $agentsDir -Filter *.toml -File).Count
    Write-Host "Installed reasflow-codex"
    Write-Host "  scope: $(if ($Global) { 'global' } else { 'local' })"
    Write-Host "  mode: $(if ($Dev) { 'dev' } else { 'release' })"
    Write-Host "  shared skills: $sharedSkillCount -> $skillsDir"
    Write-Host "  private skills: $privateSkillCount -> $privateSkillsDir"
    Write-Host "  agents: $agentCount -> $agentsDir"
    if ($configInstalled) {
        Write-Host "  config: -> $(Join-Path $targetRoot '.codex/config.toml')"
    }
    Write-Host "  manifest: $manifest"
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}

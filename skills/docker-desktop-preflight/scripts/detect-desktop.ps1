# Detect whether the active docker context is served by Docker Desktop.
#
# Algorithm (identical to detect-desktop.sh -- only the platform data
# differs; both implement references/platform-signals.md):
#   1. Note DOCKER_HOST (overrides context selection; still capture context
#      name/description as info).
#   2. Resolve the current context: name, description, docker endpoint.
#   3. Windows-containers-mode gate: `docker desktop engine ls --format json`
#      (read-only). Engine identity signals below are unverified in that
#      mode, so it is ALWAYS reported as indeterminate (never 0/1).
#   4. Authoritative: `docker info --format '{{.OperatingSystem}}'` ==
#      "Docker Desktop" -> positive; "Container Platform" -> explicitly NOT
#      Desktop (sibling product); anything else -> another runtime, name it.
#   5. Corroborate (informational only, never gates the verdict): Name
#      (shared hostname, not proof by itself); KernelVersion suffix
#      identifies the backend (-microsoft-standard-WSL2 = WSL2 backend;
#      -linuxkit = Hyper-V backend). Neither suffix while
#      OperatingSystem=Docker Desktop is an anomaly.
#   6. Daemon unreachable -> classify by context name and named-pipe
#      endpoint: dockerDesktopLinuxEngine / dockerDesktopWindowsEngine are a
#      strong Desktop signal; docker_engine alone is ambiguous (Rancher
#      Desktop/Podman also serve it) -> indeterminate. Context description
#      "Docker Desktop" is a corroborator independent of the context name.
#   7. Installation markers (tie-breakers only -- "installed != serving"):
#      `docker desktop version`, and per-machine marker paths/files.
#
# Data source: source-verified against Docker Desktop 4.85 (pre-GA); see
# references/platform-signals.md for the full signals table this implements.
#
# Read-only: only `docker context inspect`, `docker info`,
# `docker desktop version`, `docker desktop engine ls`, and filesystem
# reads. Never starts, stops, restarts, updates, enables, disables, or
# diagnoses Docker Desktop, and never touches the engine (no pulls, no
# container runs). Compatible with Windows PowerShell 5.1 (no ternary, no
# null-coalescing, no null-conditional operators).
#
# Usage: powershell -File scripts\detect-desktop.ps1
#
# Exit codes:
#   0 = Docker Desktop, verified and serving the current context
#   1 = daemon reachable but confirmed NOT Docker Desktop
#   2 = Desktop installed but daemon unreachable (offer `docker desktop
#       start` as a choice; never run it here)
#   3 = indeterminate (Windows-containers mode, or no signal was conclusive)

$ErrorActionPreference = "SilentlyContinue"

function Test-WindowsContainersMode {
    $rawLines = & docker desktop engine ls --format json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $rawLines) {
        return $false
    }
    $json = $rawLines -join "`n"
    try {
        $items = ConvertFrom-Json -InputObject $json
    } catch {
        return $false
    }
    foreach ($item in $items) {
        $isCurrent = $false
        $modeValue = ""
        foreach ($prop in $item.PSObject.Properties) {
            if ($prop.Name -eq "Current" -and $prop.Value -eq $true) { $isCurrent = $true }
            if ($prop.Name -eq "Name" -or $prop.Name -eq "Mode") { $modeValue = [string]$prop.Value }
        }
        if ($isCurrent -and $modeValue -match "windows") {
            return $true
        }
    }
    return $false
}

# Step 1: note DOCKER_HOST -- it overrides context selection entirely.
if ($env:DOCKER_HOST) {
    Write-Output "DOCKER_HOST is set: $env:DOCKER_HOST (overrides context selection)"
}

# Step 2: resolve the current context. Never enumerate installed software
# instead -- multiple contexts/runtimes routinely coexist.
$contextName = (& docker context inspect --format "{{.Name}}" 2>$null)
$socketHost = (& docker context inspect --format "{{.Endpoints.docker.Host}}" 2>$null)
$contextDesc = (& docker context inspect --format "{{.Metadata.Metadata.Description}}" 2>$null)
if (-not $contextName) { $contextName = "unknown" }
if (-not $socketHost) { $socketHost = "unknown endpoint" }
Write-Output "context: $contextName ($socketHost)"
if ($contextDesc) {
    Write-Output "context description: $contextDesc"
}

# Step 3: Windows-containers mode -- engine identity signals below are
# unverified in this mode. Always indeterminate, regardless of other signals.
if (Test-WindowsContainersMode) {
    Write-Output "Windows containers mode: engine identity signals are unverified -- treating as indeterminate"
    exit 3
}

# Step 4: ask the daemon -- authoritative signal, from whatever endpoint the
# current context actually reaches.
$osId = (& docker info --format "{{.OperatingSystem}}" 2>$null)

if ($osId) {
    if ($osId -ceq "Docker Desktop") {
        # Step 5: corroborate -- informational only, never gates the verdict.
        $name = (& docker info --format "{{.Name}}" 2>$null)
        $kernel = (& docker info --format "{{.KernelVersion}}" 2>$null)
        Write-Output "runtime: Docker Desktop (verified via docker info)"
        Write-Output "corroborated: Name=$name (shared hostname, not proof on its own)"
        if ($kernel -match "-microsoft-standard-WSL2$") {
            Write-Output "backend: WSL2 backend (KernelVersion=$kernel)"
        } elseif ($kernel -match "-linuxkit$") {
            Write-Output "backend: Hyper-V backend (KernelVersion=$kernel)"
        } else {
            Write-Output "anomaly: OperatingSystem=Docker Desktop but KernelVersion ($kernel) has neither expected suffix"
        }
        exit 0
    }
    if ($osId -ceq "Container Platform") {
        Write-Output "runtime: NOT Docker Desktop -- Container Platform is a sibling product, not Desktop"
        exit 1
    }
    Write-Output "runtime: NOT Docker Desktop -- skill does not apply (OperatingSystem=$osId)"
    exit 1
}

# Step 6: daemon unreachable (e.g. Desktop stopped) -- fall back to
# classification by context name, named pipe, and description.
Write-Output "daemon unreachable via current context; falling back to context/pipe classification"

$looksLikeDesktop = $false
$ambiguousPipe = $false

if ($contextName -eq "desktop-linux" -or $contextName -eq "desktop-windows") {
    $looksLikeDesktop = $true
}
if ($socketHost -match "dockerDesktopLinuxEngine" -or $socketHost -match "dockerDesktopWindowsEngine" -or $socketHost -match "dockerDesktopEngine") {
    Write-Output "note: named pipe is a Desktop-specific engine pipe -- strong Desktop signal"
    $looksLikeDesktop = $true
} elseif ($socketHost -match "docker_engine") {
    Write-Output "note: pipe is docker_engine -- ambiguous, also served by Rancher Desktop/Podman"
    $ambiguousPipe = $true
}
if ($contextDesc -ceq "Docker Desktop") {
    Write-Output "note: context description is 'Docker Desktop' -- corroborator independent of context name"
    $looksLikeDesktop = $true
}

# Step 7: installation markers -- tie-breakers only. These prove Desktop is
# installed, not that it serves the current context.
& docker desktop version 2>$null | Out-Null
$desktopCliOk = ($LASTEXITCODE -eq 0)

$markerOk = $false
if (Test-Path "$env:ProgramFiles\Docker\Docker") { $markerOk = $true }
if (Test-Path "$env:LOCALAPPDATA\Programs\DockerDesktop") { $markerOk = $true }
if (Test-Path "$env:APPDATA\Docker\settings-store.json") { $markerOk = $true }

if ($desktopCliOk -or $markerOk) {
    Write-Output "installation marker present (installed, not necessarily serving): docker desktop CLI ok=$desktopCliOk, marker path=$markerOk"
}

if ($looksLikeDesktop -and ($desktopCliOk -or $markerOk)) {
    Write-Output "verdict: Docker Desktop installed but not running (daemon unreachable) -- 'docker desktop start' would start it, your choice"
    exit 2
}

if ($ambiguousPipe) {
    Write-Output "verdict: indeterminate -- docker_engine pipe alone does not discriminate Desktop from other engines"
    exit 3
}

Write-Output "verdict: undetermined -- daemon unreachable and no Docker Desktop markers matched"
exit 3

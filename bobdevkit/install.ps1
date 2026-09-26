# bobdevkit installer for Windows — installs the three Bob devkit skills
# into an AI agent's skills directory.
#
# From a clone:   .\install.ps1 [-Global|-Project] [-Agent NAME] [-Dir DIR] [-Uninstall]
# One-liner:      irm https://raw.githubusercontent.com/mrgonzales-dev/ibmbob-hackathon/main/bobdevkit/install.ps1 | iex
#
# Project scope (default): installs into every detected agent config dir
# in the current directory (.bob .devin .claude .cursor); creates
# .bob\skills when none exist. Global scope installs to the agent's home
# skills dir (default: ~\.bob\skills).
[CmdletBinding()]
param(
    [switch]$Project,
    [switch]$Global,
    [string]$Agent,
    [string]$Dir,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$Repo   = "mrgonzales-dev/ibmbob-hackathon"
$Branch = "main"
$Skills = @("bob-upgrade-check", "bob-impact", "bob-pr")

function Get-AgentDir {
    param([string]$Name, [string]$Scope)
    switch ("$Name`:$Scope") {
        "bob:project"    { return ".bob" }
        "devin:project"  { return ".devin" }
        "claude:project" { return ".claude" }
        "cursor:project" { return ".cursor" }
        "bob:global"     { return "$HOME\.bob" }
        "devin:global"   { return "$HOME\.config\devin" }
        "claude:global"  { return "$HOME\.claude" }
        "cursor:global"  { return "$HOME\.cursor" }
        default          { return $null }
    }
}

# --- resolve the source tree ---------------------------------------------
# Local: this script sits inside bobdevkit\ after a clone.
# Remote: piped via iex — download the repo zip and unpack to a temp dir.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tmp = $null

if ($ScriptDir -and (Test-Path "$ScriptDir\bob-pr\SKILL.md")) {
    $Src = $ScriptDir
} else {
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("bobdevkit-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Tmp | Out-Null
    $zip = Join-Path $Tmp "repo.zip"
    Write-Host "Downloading bobdevkit from github.com/$Repo@$Branch"
    Invoke-WebRequest "https://codeload.github.com/$Repo/zip/refs/heads/$Branch" -OutFile $zip
    Expand-Archive $zip -DestinationPath $Tmp
    $Src = Join-Path $Tmp "ibmbob-hackathon-$Branch\bobdevkit"
    if (-not (Test-Path $Src)) { throw "install.ps1: package missing in archive" }
}

foreach ($s in $Skills) {
    if (-not (Test-Path "$Src\$s\SKILL.md")) {
        throw "install.ps1: $s\SKILL.md not found in source"
    }
}

# --- resolve the target skills dirs ---------------------------------------
$Scope = if ($Global) { "global" } else { "project" }
$Targets = @()

if ($Dir) {
    $Targets = @($Dir)
} elseif ($Agent) {
    $base = Get-AgentDir $Agent $Scope
    if (-not $base) { throw "install.ps1: unknown agent '$Agent' (bob|devin|claude|cursor)" }
    $Targets = @("$base\skills")
} elseif ($Scope -eq "global") {
    $Targets = @("$HOME\.bob\skills")
} else {
    foreach ($cfg in ".bob", ".devin", ".claude", ".cursor") {
        if (Test-Path $cfg) { $Targets += "$cfg\skills" }
    }
    if ($Targets.Count -eq 0) {
        $Targets = @(".\.bob\skills")
        Write-Host "No agent config dir found - defaulting to .bob\skills"
    }
}

# --- install / uninstall ---------------------------------------------------
try {
    foreach ($target in $Targets) {
        if ($Uninstall) {
            foreach ($s in $Skills) {
                $path = Join-Path $target $s
                if (Test-Path $path) {
                    Remove-Item -Recurse -Force $path
                    Write-Host "Removed $s from $path"
                }
            }
            continue
        }
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        foreach ($s in $Skills) {
            $dest = Join-Path $target $s
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            Copy-Item -Recurse "$Src\$s" $dest
            Get-ChildItem -Recurse $dest -Include "__pycache__", "*.pyc" -Force |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Installed $s into $dest"
        }
    }
} finally {
    if ($Tmp) { Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue }
}

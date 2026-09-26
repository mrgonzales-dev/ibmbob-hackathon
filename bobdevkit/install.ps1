# bobdevkit installer for Windows — installs the Bob devkit skills
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
    [switch]$Uninstall,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

$Repo      = "mrgonzales-dev/ibmbob-hackathon"
$Branch    = "main"
$AllSkills = @("bob-upgrade-check", "bob-impact", "bob-pr")
$Color     = -not $env:NO_COLOR -and [Environment]::UserInteractive

function Write-Banner {
    if (-not $Color) { return }
    Write-Host ""
    @(
        "██████╗  ██████╗ ██████╗     ██████╗ ███████╗██╗   ██╗██╗  ██╗██╗████████╗",
        "██╔══██╗██╔═══██╗██╔══██╗    ██╔══██╗██╔════╝██║   ██║██║ ██╔╝██║╚══██╔══╝",
        "██████╔╝██║   ██║██████╔╝    ██║  ██║█████╗  ██║   ██║█████╔╝ ██║   ██║   ",
        "██╔══██╗██║   ██║██╔══██╗    ██║  ██║██╔══╝  ╚██╗ ██╔╝██╔═██╗ ██║   ██║   ",
        "██████╔╝╚██████╔╝██████╔╝    ██████╔╝███████╗ ╚████╔╝ ██║  ██╗██║   ██║   ",
        "╚═════╝  ╚═════╝ ╚═════╝     ╚═════╝ ╚══════╝  ╚═══╝  ╚═╝  ╚═╝╚═╝   ╚═╝   "
    ) | ForEach-Object { Write-Host $_ -ForegroundColor Magenta }
    Write-Host "  terminal-native skills for your AI agent" -ForegroundColor DarkGray
    Write-Host ""
}

function Write-Step { param([string]$Msg) Write-Host $Msg -ForegroundColor DarkGray }
function Write-Ok   { param([string]$Msg) Write-Host "✓ $Msg" -ForegroundColor Green }

function Get-AgentDir {
    param([string]$Name, [string]$Scope)
    switch ("$Name`:$Scope") {
        "bob:project"      { return ".bob" }
        "devin:project"    { return ".devin" }
        "claude:project"   { return ".claude" }
        "cursor:project"   { return ".cursor" }
        "windsurf:project" { return ".codeium\windsurf" }
        "bob:global"       { return "$HOME\.bob" }
        "devin:global"     { return "$HOME\.config\devin" }
        "claude:global"    { return "$HOME\.claude" }
        "cursor:global"    { return "$HOME\.cursor" }
        "windsurf:global"  { return "$HOME\.codeium\windsurf" }
        default            { return $null }
    }
}

Write-Banner

# --- resolve the source tree ---------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tmp = $null

if ($ScriptDir -and (Test-Path "$ScriptDir\bob-pr\SKILL.md")) {
    $Src = $ScriptDir
} else {
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("bobdevkit-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $Tmp | Out-Null
    $zip = Join-Path $Tmp "repo.zip"
    Write-Step "downloading bobdevkit from github.com/$Repo@$Branch"
    Invoke-WebRequest "https://codeload.github.com/$Repo/zip/refs/heads/$Branch" -OutFile $zip
    Expand-Archive $zip -DestinationPath $Tmp
    $Src = Join-Path $Tmp "ibmbob-hackathon-$Branch\bobdevkit"
    if (-not (Test-Path $Src)) { throw "install.ps1: package missing in archive" }
}

# --- pick the skills -------------------------------------------------------
$Skills = $AllSkills
if (-not $Yes -and -not $Uninstall -and [Environment]::UserInteractive) {
    Write-Host "? which skills? (numbers, space/comma separated — Enter for all)" -ForegroundColor Blue
    for ($i = 0; $i -lt $AllSkills.Count; $i++) {
        Write-Host ("  {0}) {1}" -f ($i + 1), $AllSkills[$i]) -ForegroundColor Magenta
    }
    $answer = Read-Host ">"
    if ($answer) {
        $picked = @()
        foreach ($n in ($answer -split '[,\s]+' | Where-Object { $_ })) {
            $idx = 0
            if ([int]::TryParse($n, [ref]$idx) -and $idx -ge 1 -and $idx -le $AllSkills.Count) {
                $picked += $AllSkills[$idx - 1]
            }
        }
        if ($picked.Count -eq 0) { Write-Host "no skills picked — nothing to do"; exit 0 }
        $Skills = $picked
    }
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
    if (-not $base) { throw "install.ps1: unknown agent '$Agent' (bob|devin|claude|cursor|windsurf)" }
    $Targets = @("$base\skills")
} elseif ($Scope -eq "global") {
    $Targets = @("$HOME\.bob\skills")
} else {
    $found = @()
    foreach ($cfg in ".bob", ".devin", ".claude", ".cursor", ".codeium\windsurf") {
        if (Test-Path $cfg) { $found += $cfg; $Targets += "$cfg\skills" }
    }
    if ($found.Count -gt 0) {
        Write-Step "detecting agent environments…"
        Write-Step ("  found: " + ($found -join ","))
        if (-not $Yes -and [Environment]::UserInteractive) {
            Write-Host "? install into which? (number — Enter for all detected)" -ForegroundColor Blue
            for ($i = 0; $i -lt $Targets.Count; $i++) {
                Write-Host ("  {0}) {1}" -f ($i + 1), $Targets[$i]) -ForegroundColor Magenta
            }
            $answer = Read-Host ">"
            if ($answer -and [int]::TryParse($answer, [ref]($idx = 0)) -and
                $idx -ge 1 -and $idx -le $Targets.Count) {
                $Targets = @($Targets[$idx - 1])
            }
        }
    } else {
        $Targets = @(".\.bob\skills")
        Write-Step "no agent config dir found — defaulting to .bob\skills"
    }
}

# --- install / uninstall ---------------------------------------------------
try {
    foreach ($target in $Targets) {
        if ($Uninstall) {
            foreach ($s in $AllSkills) {
                $path = Join-Path $target $s
                if (Test-Path $path) {
                    Remove-Item -Recurse -Force $path
                    Write-Ok "removed $s from $path"
                }
            }
            continue
        }
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Write-Step "installing into $target"
        foreach ($s in $Skills) {
            $dest = Join-Path $target $s
            if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
            Copy-Item -Recurse "$Src\$s" $dest
            Get-ChildItem -Recurse $dest -Include "__pycache__", "*.pyc" -Force |
                Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
            Write-Ok "$s installed"
        }
    }
    if (-not $Uninstall) { Write-Host ""; Write-Ok "done — restart your agent" }
} finally {
    if ($Tmp) { Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue }
}

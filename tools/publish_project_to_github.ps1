[CmdletBinding()]
param(
    [string]$RepoUrl = "https://github.com/Nedric53/Moving_centers_of_Yerevan.git",
    [string]$Branch = "main",
    [string]$PythonExe = "C:\Users\Nedric\anaconda3\python.exe",
    [string]$GitExe = "",
    [string]$GitName = "",
    [string]$GitEmail = "",
    [switch]$FreshStart,
    [switch]$SkipBuild,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$rebuildScript = Join-Path $scriptDir "rebuild_release_site.py"
$publishScript = Join-Path $repoRoot "src\armenia_modular\publish_github_pages.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (-not $SkipBuild) {
    & $PythonExe $rebuildScript
    if ($LASTEXITCODE -ne 0) {
        throw "Release rebuild failed."
    }
}

$publishArgs = @(
    $publishScript,
    "--repo-root", $repoRoot,
    "--site-dir", "data/build/site",
    "--docs-dir", "docs",
    "--remote-url", $RepoUrl,
    "--branch", $Branch,
    "--commit-message", $(if ($FreshStart) { "Initial clean publish" } else { "Update project and release site" })
)

if ($GitExe) {
    $publishArgs += @("--git-exe", $GitExe)
}
if ($GitName) {
    $publishArgs += @("--git-name", $GitName)
}
if ($GitEmail) {
    $publishArgs += @("--git-email", $GitEmail)
}
if ($FreshStart) {
    $publishArgs += "--fresh-start"
}
if (-not $SkipPush) {
    $publishArgs += "--push"
}

& $PythonExe @publishArgs
if ($LASTEXITCODE -ne 0) {
    throw "GitHub publish failed."
}

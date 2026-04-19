$projectRoot = $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Local Document Assistant.lnk"
$targetPath = Join-Path $projectRoot "run_app.bat"

# Icon priority:
# 1) project-local icon at .\assets\app.ico (or .\assets\icon.ico)
# 2) Ollama app icon
# 3) Docker Desktop icon
# 4) built-in Windows app icon fallback
$projectIconPath = Join-Path $projectRoot "assets\app.ico"
$alternateProjectIconPath = Join-Path $projectRoot "assets\icon.ico"
$iconLocation = "$env:SystemRoot\System32\imageres.dll,15"

if (Test-Path $projectIconPath) {
    $iconLocation = $projectIconPath
} elseif (Test-Path $alternateProjectIconPath) {
    $iconLocation = $alternateProjectIconPath
} elseif (Test-Path "$env:LocalAppData\Programs\Ollama\ollama app.exe") {
    $iconLocation = "$env:LocalAppData\Programs\Ollama\ollama app.exe,0"
} elseif (Test-Path "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe") {
    $iconLocation = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe,0"
}

if (-not (Test-Path $targetPath)) {
    Write-Error "run_app.bat not found in project root: $projectRoot"
    exit 1
}

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $projectRoot
$shortcut.IconLocation = $iconLocation
$shortcut.Description = "Launch Local Document Assistant app"
$shortcut.Save()

Write-Host "Shortcut created: $shortcutPath"
Write-Host "Icon used: $iconLocation"

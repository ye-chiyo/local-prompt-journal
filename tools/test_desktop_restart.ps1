[CmdletBinding()]
param(
    [switch]$Run,
    [switch]$Worker,
    [string]$OutputDirectory,
    [string]$TaskName,
    [string]$DataDirectory,
    [string]$CollectorDataArgument,
    [ValidateRange(0, 120)][int]$DelaySeconds = 20,
    [ValidateRange(15, 180)][int]$TimeoutSeconds = 75
)

# Run this file with Windows PowerShell 5.1. Default mode only inspects state.
# -Run schedules an independent, hidden worker before restarting the desktop.
$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$baseUrl = 'http://127.0.0.1:8766'

function Get-PhysicalFilePath([string]$Path) {
    # MSIX may redirect AppData writes. Task Scheduler sees the physical path.
    if (-not ('RestartTestNativePath' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class RestartTestNativePath {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern uint GetFinalPathNameByHandle(SafeFileHandle handle,
        StringBuilder path, uint count, uint flags);
}
'@
    }
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        $buffer = New-Object Text.StringBuilder 32768
        $length = [RestartTestNativePath]::GetFinalPathNameByHandle($stream.SafeFileHandle, $buffer, 32768, 0)
        if ($length -eq 0 -or $length -ge 32768) { throw 'Cannot resolve the physical file path.' }
        $resolved = $buffer.ToString()
        if ($resolved.StartsWith('\\?\UNC\')) { return '\\' + $resolved.Substring(8) }
        if ($resolved.StartsWith('\\?\')) { return $resolved.Substring(4) }
        return $resolved
    } finally { $stream.Dispose() }
}

function Get-DesktopIdentity {
    $packages = @(Get-AppxPackage -Name OpenAI.Codex)
    if ($packages.Count -ne 1) { throw 'Expected exactly one installed OpenAI.Codex package.' }
    $package = $packages[0]
    $manifest = Get-AppxPackageManifest -Package $package
    $application = @($manifest.Package.Applications.Application | Where-Object {
        $_.Executable -match '(^|[/\\])ChatGPT\.exe$'
    })
    if ($application.Count -ne 1) { throw 'Cannot resolve the desktop application from its manifest.' }
    $executable = Join-Path $package.InstallLocation $application[0].Executable
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { throw 'Desktop executable is missing.' }
    return [pscustomobject]@{
        Executable = $executable
        AppUserModelId = $package.PackageFamilyName + '!' + $application[0].Id
    }
}

if (-not $DataDirectory) {
    $candidates = @((Join-Path $env:LOCALAPPDATA 'LocalPromptJournal\data'),
        (Join-Path $env:LOCALAPPDATA 'Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\LocalPromptJournal\data'))
    $existing = @($candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'journal.sqlite3') } |
        ForEach-Object { Split-Path -Parent (Get-PhysicalFilePath (Join-Path $_ 'journal.sqlite3')) } | Select-Object -Unique)
    if ($existing.Count -gt 1) { throw 'Multiple databases found. Specify -DataDirectory explicitly.' }
    if ($existing.Count -eq 1) { $DataDirectory = $existing[0] }
    else { $DataDirectory = $candidates[0] }
}
if (-not $CollectorDataArgument) { $CollectorDataArgument = $DataDirectory }

function Get-DesktopProcesses {
    return @(Get-CimInstance Win32_Process -Filter "Name='ChatGPT.exe'" | Where-Object {
        $_.ExecutablePath -ieq $script:desktop.Executable
    })
}

function Read-CollectorStatus {
    try {
        $status = Invoke-RestMethod -Uri "$baseUrl/api/status" -TimeoutSec 4
        # Do not copy message bodies, evidence or the session list into the report.
        return [pscustomobject]@{
            running = $status.running
            sourceAvailable = $status.sourceAvailable
            error = $status.error
            enabledAt = $status.enabledAt
            lastSuccessAt = $status.lastSuccessAt
        }
    } catch { return $null }
}

function Get-MonitorProcess {
    $pidFile = Join-Path $dataDirectory 'desktop-monitor.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $monitorId = 0
    if (-not [int]::TryParse((Get-Content -LiteralPath $pidFile -Raw).Trim(), [ref]$monitorId)) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId=$monitorId" | Where-Object {
        $_.Name -ieq 'pythonw.exe' -and $_.CommandLine -like '*desktop_monitor.py*'
    }
}

function Get-CollectorListener {
    return @(Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Condition([scriptblock]$Condition, [string]$Description) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for $Description ($TimeoutSeconds seconds)."
}

function Write-Report {
    $script:report.updatedAt = [DateTimeOffset]::Now.ToString('o')
    $temporary = Join-Path $OutputDirectory 'result.json.tmp'
    $destination = Join-Path $OutputDirectory 'result.json'
    $script:report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $destination -Force
    $lines = @('# Codex desktop restart test', '', "Result: $($script:report.result)",
        "Updated: $($script:report.updatedAt)", '', "Website: $baseUrl/", '',
        'This tests process restart and collector recovery. It does not certify Windows logon startup,',
        'new dialogue ingestion, or orderly app shutdown. Desktop processes are forcibly stopped.', '')
    foreach ($check in $script:report.checks) {
        $lines += "- [$($check.outcome)] $($check.name): $($check.detail)"
    }
    if ($script:report.error) { $lines += @('', "Error: $($script:report.error)") }
    if ($script:report.recoveryError) { $lines += @('', "App recovery error: $($script:report.recoveryError)") }
    $lines | Set-Content -LiteralPath (Join-Path $OutputDirectory 'result.md') -Encoding UTF8
}

function Add-Check([string]$Name, [string]$Outcome, [string]$Detail) {
    $script:report.checks += [pscustomobject]@{
        name = $Name; outcome = $Outcome; detail = $Detail
        at = [DateTimeOffset]::Now.ToString('o')
    }
    Write-Report
}

function Start-Desktop {
    # Activate the installed package using the Windows shell, with no console.
    $shell = New-Object -ComObject Shell.Application
    $shell.ShellExecute('explorer.exe', ('shell:AppsFolder\' + $script:desktop.AppUserModelId), '', 'open', 1)
}

function Assert-Preconditions {
    $script:desktop = Get-DesktopIdentity
    $processes = @(Get-DesktopProcesses)
    $mainProcesses = @($processes | Where-Object { $_.CommandLine -notmatch '--type=' })
    if ($mainProcesses.Count -ne 1) { throw 'Expected one running desktop main process; no restart was performed.' }
    $monitor = Get-MonitorProcess
    if (-not $monitor) { throw 'The desktop monitor is not running. Repair it with: python -m prompt_journal install-autostart' }
    $status = Read-CollectorStatus
    if (-not $status -or -not $status.running -or -not $status.sourceAvailable -or $status.error) {
        throw 'The collector must be healthy before restarting the desktop.'
    }
    if (-not $status.enabledAt -or -not $status.lastSuccessAt) { throw 'Collector status lacks its existing capture scope.' }
    $listeners = @(Get-CollectorListener)
    if ($listeners.Count -ne 1) { throw 'Expected exactly one collector listener on port 8766.' }
    $ownerId = $listeners[0].OwningProcess
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerId"
    if (-not $owner -or $owner.ParentProcessId -ne $monitor.ProcessId -or
        $owner.CommandLine -notlike '*-m prompt_journal*' -or $owner.CommandLine -notlike "*$CollectorDataArgument*") {
        throw 'Port 8766 is not owned by this monitor and data directory; no restart was performed.'
    }
    return [pscustomobject]@{
        DesktopPid = $mainProcesses[0].ProcessId; MonitorPid = $monitor.ProcessId
        CollectorPid = $ownerId; Status = $status; DataDirectory = $dataDirectory
        AppUserModelId = $script:desktop.AppUserModelId
    }
}

if (-not $Worker) {
    $baseline = Assert-Preconditions
    if (-not $Run) {
        [pscustomobject]@{ mode = 'preflight-only'; baseline = $baseline
            next = 'Use -Run to schedule the real desktop restart test.' } | ConvertTo-Json -Depth 5
        exit 0
    }
    if (-not $OutputDirectory) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $OutputDirectory = Join-Path $env:LOCALAPPDATA "LocalPromptJournal\verification\desktop-restart-$stamp-$([guid]::NewGuid().ToString('N').Substring(0,8))"
    }
    $OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
    if (Test-Path -LiteralPath $OutputDirectory) { throw 'Choose a new output directory; existing reports are never overwritten.' }
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
    $workerPath = Join-Path $OutputDirectory 'restart-worker.ps1'
    Copy-Item -LiteralPath $PSCommandPath -Destination $workerPath
    $workerPath = Get-PhysicalFilePath $workerPath
    $OutputDirectory = Split-Path -Parent $workerPath
    $DataDirectory = Split-Path -Parent (Get-PhysicalFilePath (Join-Path $DataDirectory 'journal.sqlite3'))
    $TaskName = 'LocalPromptJournal-RestartTest-' + [guid]::NewGuid().ToString('N')
    $service = New-Object -ComObject Schedule.Service
    $service.Connect()
    $folder = $service.GetFolder('\')
    $task = $service.NewTask(0)
    $task.RegistrationInfo.Description = 'One-shot Codex restart and local journal following verification.'
    $task.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $task.Principal.LogonType = 3 # interactive token; no password or elevation
    $task.Principal.RunLevel = 0
    $task.Settings.Hidden = $true
    $task.Settings.AllowDemandStart = $true
    $task.Settings.DisallowStartIfOnBatteries = $false
    $task.Settings.StopIfGoingOnBatteries = $false
    $task.Settings.ExecutionTimeLimit = 'PT10M'
    $action = $task.Actions.Create(0)
    # Run a saved copy from the report directory, without depending on a source
    # drive or a Python runtime being visible in Task Scheduler's environment.
    $action.Path = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = @('-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass',
        '-File', $workerPath, '-Worker', '-OutputDirectory', $OutputDirectory,
        '-TaskName', $TaskName, '-DataDirectory', $DataDirectory, '-CollectorDataArgument', $CollectorDataArgument,
        '-DelaySeconds', "$DelaySeconds", '-TimeoutSeconds', "$TimeoutSeconds")
    $action.Arguments = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $action.WorkingDirectory = $OutputDirectory
    $task.XmlText | Set-Content -LiteralPath (Join-Path $OutputDirectory 'scheduled-task.xml') -Encoding UTF8
    $registered = $null
    try {
        $registered = $folder.RegisterTaskDefinition($TaskName, $task, 2, $null, $null, 3)
        $scheduled = [pscustomobject]@{ taskName = $TaskName; reportDirectory = $OutputDirectory
            delaySeconds = $DelaySeconds; baseline = $baseline; scheduledAt = [DateTimeOffset]::Now.ToString('o') }
        $scheduled | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'scheduled.json') -Encoding UTF8
        $null = $registered.Run($null)
        $ready = [Diagnostics.Stopwatch]::StartNew()
        while (-not (Test-Path -LiteralPath (Join-Path $OutputDirectory 'result.json'))) {
            if ($ready.Elapsed.TotalSeconds -gt 12) { throw 'Scheduled worker did not write its startup report; desktop restart has not been verified.' }
            Start-Sleep -Milliseconds 250
        }
        $scheduled | ConvertTo-Json -Depth 6
    } catch {
        [pscustomobject]@{ result = 'LAUNCH_FAILED'; error = $_.Exception.Message
            taskState = $(if ($registered) {$registered.State} else {$null})
            taskResult = $(if ($registered) {$registered.LastTaskResult} else {$null}) } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'launch-error.json') -Encoding UTF8
        if ($registered) { $folder.DeleteTask($TaskName, 0) }
        throw
    }
    exit 0
}

if (-not $OutputDirectory -or -not (Test-Path -LiteralPath $OutputDirectory -PathType Container)) {
    throw 'The worker requires the output directory created by -Run.'
}
$report = [ordered]@{ result = 'RUNNING'; startedAt = [DateTimeOffset]::Now.ToString('o')
    updatedAt = $null; checks = @(); baseline = $null; after = $null; error = $null; recoveryError = $null }
$restartAttempted = $false
try {
    Add-Check 'worker' 'PASS' "Independent worker started; waiting $DelaySeconds seconds before restart."
    Start-Sleep -Seconds $DelaySeconds
    $baseline = Assert-Preconditions
    $report.baseline = $baseline
    Add-Check 'preconditions' 'PASS' "Desktop=$($baseline.DesktopPid); monitor=$($baseline.MonitorPid); collector=$($baseline.CollectorPid)."
    $restartAttempted = $true
    # Stop only processes whose full executable path matches the installed package.
    foreach ($process in @(Get-DesktopProcesses | Where-Object { $_.CommandLine -notmatch '--type=' })) {
        $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ProcessId)"
        if ($live -and $live.ExecutablePath -ieq $desktop.Executable) {
            Stop-Process -Id $live.ProcessId -Force
        }
    }
    Wait-Condition { @(Get-DesktopProcesses | Where-Object { $_.CommandLine -notmatch '--type=' }).Count -eq 0 } 'desktop main process exit'
    Add-Check 'desktop-exit' 'PASS' 'The desktop main process exited; auxiliary processes do not count as the main app.'
    Wait-Condition { @(Get-CollectorListener).Count -eq 0 -and -not (Get-Process -Id $baseline.CollectorPid -ErrorAction SilentlyContinue) } 'collector and listener shutdown'
    # Leave an additional interval to detect accidental collector respawn while the app is down.
    Start-Sleep -Seconds 3
    if (@(Get-CollectorListener).Count -ne 0) { throw 'Collector restarted while the desktop was closed.' }
    $monitor = Get-MonitorProcess
    if (-not $monitor -or $monitor.ProcessId -ne $baseline.MonitorPid) { throw 'The original monitor did not survive desktop exit.' }
    Add-Check 'collector-stopped' 'PASS' 'Old collector exited, port 8766 closed and the original monitor remained alive.'
    Start-Desktop
    Wait-Condition { @(Get-DesktopProcesses | Where-Object { $_.CommandLine -notmatch '--type=' }).Count -eq 1 } 'desktop relaunch'
    Add-Check 'desktop-reopened' 'PASS' 'The desktop was reopened using its installed package identity.'
    Wait-Condition {
        $current = Read-CollectorStatus
        $current -and $current.running -and $current.sourceAvailable -and -not $current.error -and
            $current.lastSuccessAt -and ([DateTimeOffset]::Parse($current.lastSuccessAt) -gt [DateTimeOffset]::Parse($baseline.Status.lastSuccessAt))
    } 'automatic collection recovery and a new successful collection'
    $after = Assert-Preconditions
    $report.after = $after
    if ($after.DesktopPid -eq $baseline.DesktopPid -or $after.CollectorPid -eq $baseline.CollectorPid) {
        throw 'Expected replacement desktop and collector processes.'
    }
    if ($after.MonitorPid -ne $baseline.MonitorPid) { throw 'Expected the original monitor to survive without manual restart.' }
    if ($after.Status.enabledAt -ne $baseline.Status.enabledAt) { throw 'The saved capture enable time changed.' }
    $page = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing -TimeoutSec 5
    if ($page.StatusCode -ne 200) { throw 'Journal website did not return HTTP 200.' }
    Add-Check 'automatic-recovery' 'PASS' 'New collector owned by the same monitor; source available, no error, new successful scan and HTTP 200.'
    Add-Check 'capture-scope' 'PASS' 'Existing data directory and enabledAt preserved; no manual monitor or collector launch was used.'
    $report.result = 'PASS'
} catch {
    $report.result = 'FAIL'
    $report.error = $_.Exception.Message
    Add-Check 'failure' 'FAIL' $report.error
} finally {
    if ($restartAttempted) {
        try {
            if (@(Get-DesktopProcesses | Where-Object { $_.CommandLine -notmatch '--type=' }).Count -eq 0) {
                Start-Desktop
                Wait-Condition { @(Get-DesktopProcesses | Where-Object { $_.CommandLine -notmatch '--type=' }).Count -gt 0 } 'app recovery after failure'
                Add-Check 'app-recovery' 'INFO' 'Desktop reopened after failure; test result remains FAIL.'
            }
        } catch { $report.recoveryError = $_.Exception.Message }
    }
    Write-Report
    if ($TaskName) {
        try {
            $service = New-Object -ComObject Schedule.Service
            $service.Connect()
            $service.GetFolder('\').DeleteTask($TaskName, 0)
        } catch {
            Add-Check 'temporary-task-cleanup' 'INFO' "Remove temporary task manually: $TaskName; $($_.Exception.Message)"
        }
    }
}
if ($report.result -ne 'PASS') { exit 1 }

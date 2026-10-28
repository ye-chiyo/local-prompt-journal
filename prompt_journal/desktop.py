"""Follow the ChatGPT desktop process and supervise the local collector."""
from __future__ import annotations

import json
import base64
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Protocol
import winreg
import uuid


TASK_NAME = "LocalPromptJournal ChatGPT Desktop Monitor"
SHORTCUT_NAME = f"{TASK_NAME}.lnk"
POLL_SECONDS = 2.0
WEBSITE_URL = "http://127.0.0.1:8766/"


def install_website_shortcuts() -> list[str]:
    """Create visible browser shortcuts outside the desktop app's MSIX redirection."""
    if os.name != "nt":
        raise RuntimeError("网站快捷方式目前仅支持 Windows。")
    from .app import default_data_dir
    output = default_data_dir().parent / "verification" / ("website-shortcuts-" + uuid.uuid4().hex)
    output.mkdir(parents=True)
    output = output.resolve()
    report_path = output / "result.json"
    task_name = "LocalPromptJournal-WebsiteShortcuts-" + uuid.uuid4().hex
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    payload = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$result = $null",
        "try {",
        "  $paths = @()",
        "  $shell = New-Object -ComObject WScript.Shell",
        "  foreach ($folder in @([Environment]::GetFolderPath('DesktopDirectory'), [Environment]::GetFolderPath('Programs'))) {",
        "    if (-not $folder) { throw 'Windows shortcut folder is unavailable.' }",
        "    $null = New-Item -ItemType Directory -Path $folder -Force",
        "    $path = Join-Path $folder 'Codex 日志.lnk'",
        "    $shortcut = $shell.CreateShortcut($path)",
        "    if ((Test-Path -LiteralPath $path) -and ($shortcut.Arguments -ne '" + WEBSITE_URL + "' -or $shortcut.TargetPath -ine ($env:SystemRoot + '\\explorer.exe'))) { throw ('An unrelated shortcut already exists: ' + $path) }",
        "    $shortcut.TargetPath = $env:SystemRoot + '\\explorer.exe'",
        "    $shortcut.Arguments = '" + WEBSITE_URL + "'",
        "    $shortcut.Description = '打开本机 Codex 日志网站'",
        "    $shortcut.IconLocation = $env:SystemRoot + '\\System32\\url.dll,0'",
        "    $shortcut.Save()",
        "    $old = Join-Path $folder 'Codex 日志.url'",
        "    if ((Test-Path -LiteralPath $old) -and ([IO.File]::ReadAllText($old) -match '(?m)^URL=http://127\\.0\\.0\\.1:8766/\\r?$')) { Remove-Item -LiteralPath $old }",
        "    $paths += $path",
        "  }",
        "  $result = @{success=$true; paths=$paths}",
        "} catch { $result = @{success=$false; error=$_.Exception.Message} }",
        "$result | ConvertTo-Json | Set-Content -LiteralPath " + quote(str(report_path) + ".tmp") + " -Encoding UTF8",
        "Move-Item -LiteralPath " + quote(str(report_path) + ".tmp") + " -Destination " + quote(report_path) + " -Force",
        "$service = New-Object -ComObject Schedule.Service; $service.Connect()",
        "$service.GetFolder('\\').DeleteTask(" + quote(task_name) + ", 0)",
    ])
    encoded = base64.b64encode(payload.encode("utf-16-le")).decode("ascii")
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$service = New-Object -ComObject Schedule.Service; $service.Connect()",
        "$task = $service.NewTask(0)",
        "$task.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$task.Principal.LogonType = 3; $task.Principal.RunLevel = 0",
        "$task.Settings.Hidden = $true; $task.Settings.ExecutionTimeLimit = 'PT1M'",
        "$task.Settings.DisallowStartIfOnBatteries = $false; $task.Settings.StopIfGoingOnBatteries = $false",
        "$action = $task.Actions.Create(0)",
        "$action.Path = $env:SystemRoot + '\\System32\\WindowsPowerShell\\v1.0\\powershell.exe'",
        "$action.Arguments = '-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand " + encoded + "'",
        "$action.WorkingDirectory = $env:SystemRoot",
        "$registered = $service.GetFolder('\\').RegisterTaskDefinition(" + quote(task_name) + ", $task, 2, $null, $null, 3)",
        "$null = $registered.Run($null)",
    ])
    completed = _run_powershell(script)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "创建网站快捷方式任务失败。")
    deadline = time.monotonic() + 20
    while not report_path.is_file() and time.monotonic() < deadline:
        time.sleep(0.25)
    if not report_path.is_file():
        raise TimeoutError(f"网站快捷方式任务尚未返回结果：{report_path}")
    result = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if not result["success"]:
        raise RuntimeError(result["error"])
    return [str(path) for path in result["paths"]]


class ChildProcess(Protocol):
    def poll(self) -> int | None: ...


class DesktopSupervisor:
    def __init__(self, desktop_running: Callable[[], bool], start_collector: Callable[[], ChildProcess],
                 stop_collector: Callable[[ChildProcess], None]):
        self.desktop_running = desktop_running
        self.start_collector = start_collector
        self.stop_collector = stop_collector
        self.collector: ChildProcess | None = None

    def step(self) -> None:
        if not self.desktop_running():
            if self.collector is not None:
                self.stop_collector(self.collector)
                self.collector = None
            return
        if self.collector is None or self.collector.poll() is not None:
            self.collector = self.start_collector()


def startup_task_action(pythonw: str, repository: str) -> str:
    entrypoint = str(Path(repository) / "tools" / "desktop_monitor.py")
    return f'"{pythonw}" "{entrypoint}"'


def startup_shortcut_path() -> Path:
    roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / SHORTCUT_NAME


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, encoding="utf-8", timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def resolve_desktop_executable() -> Path:
    repository = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages")
    try:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(repository, index)
                index += 1
            except OSError:
                break
            if not name.startswith("OpenAI.Codex_"):
                continue
            package = winreg.OpenKey(repository, name)
            try:
                root, _ = winreg.QueryValueEx(package, "PackageRootFolder")
            finally:
                winreg.CloseKey(package)
            executable = Path(root) / "app" / "ChatGPT.exe"
            if executable.is_file():
                return executable.resolve()
    finally:
        winreg.CloseKey(repository)
    raise RuntimeError("找不到 ChatGPT 桌面应用 OpenAI.Codex 的安装目录。")


def desktop_is_running(executable: Path) -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    class ProcessEntry32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                   wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    entry = ProcessEntry32()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        if kernel.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.casefold() == executable.name.casefold():
                    path = _process_image_path(kernel, entry.th32ProcessID)
                    if path.casefold() == str(executable).casefold():
                        command = _process_command_line(kernel, entry.th32ProcessID)
                        if command is not None and is_desktop_main_process(
                                {"ExecutablePath": path, "CommandLine": command}, executable):
                            return True
                if not kernel.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel.CloseHandle(snapshot)
    return False


def _process_command_line(kernel: Any, pid: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    class UnicodeString(ctypes.Structure):
        _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT),
                    ("Buffer", ctypes.c_void_p)]

    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        query = ctypes.WinDLL("ntdll").NtQueryInformationProcess
        query.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p,
                          wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
        query.restype = ctypes.c_long
        required = wintypes.ULONG()
        query(handle, 60, None, 0, ctypes.byref(required))
        if not required.value:
            return None
        buffer = ctypes.create_string_buffer(required.value)
        if query(handle, 60, buffer, required.value, ctypes.byref(required)) != 0:
            return None
        command = UnicodeString.from_buffer(buffer)
        return ctypes.wstring_at(command.Buffer, command.Length // 2)
    finally:
        kernel.CloseHandle(handle)


def _process_image_path(kernel: Any, pid: int) -> str:
    import ctypes
    from ctypes import wintypes
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        kernel.CloseHandle(handle)


def is_desktop_main_process(process: object, executable: Path) -> bool:
    if not isinstance(process, dict):
        return False
    return (str(process.get("ExecutablePath", "")).casefold() == str(executable).casefold()
            and "--type=" not in str(process.get("CommandLine", "")))


def _python_console_executable() -> str:
    executable = Path(sys.executable)
    if executable.name.casefold() == "pythonw.exe":
        executable = executable.with_name("python.exe")
    return str(executable)


def _write_monitor_log(data_dir: Path, message: str) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / "desktop-monitor.log").open("a", encoding="utf-8") as stream:
        stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def run_monitor(repository: Path, data_dir: Path, interval: float = POLL_SECONDS) -> None:
    if os.name != "nt":
        raise RuntimeError("桌面联动监视器目前仅支持 Windows。")
    import msvcrt

    data_dir.mkdir(parents=True, exist_ok=True)
    lock = (data_dir / "desktop-monitor.lock").open("a+b")
    try:
        lock.seek(0)
        if lock.read(1) == b"":
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return

        try:
            executable = resolve_desktop_executable()
        except Exception as exc:
            _write_monitor_log(data_dir, f"cannot resolve ChatGPT executable: {exc}")
            raise
        python = _python_console_executable()
        stop_signal = data_dir / "desktop-monitor.stop"
        exit_signal = data_dir / "desktop-monitor.exit"
        pid_file = data_dir / "desktop-monitor.pid"
        pid_file.write_text(str(os.getpid()), encoding="ascii")

        def start_collector() -> subprocess.Popen[bytes]:
            stop_signal.unlink(missing_ok=True)
            child = subprocess.Popen([python, "-m", "prompt_journal", "--data-dir", str(data_dir),
                "run", "--port", "8766", "--stop-file", str(stop_signal)], cwd=repository,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
            _write_monitor_log(data_dir, f"collector started pid={child.pid}")
            return child

        def stop_collector(child: ChildProcess) -> None:
            process = child
            if not isinstance(process, subprocess.Popen):
                return
            stop_signal.touch()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)
            stop_signal.unlink(missing_ok=True)
            _write_monitor_log(data_dir, "collector stopped")

        supervisor = DesktopSupervisor(lambda: desktop_is_running(executable), start_collector, stop_collector)
        _write_monitor_log(data_dir, "monitor started")
        try:
            while not exit_signal.exists():
                try:
                    supervisor.step()
                except Exception as exc:
                    _write_monitor_log(data_dir, f"monitor check failed: {exc}")
                if exit_signal.exists():
                    break
                time.sleep(interval)
            if supervisor.collector is not None:
                stop_collector(supervisor.collector)
                supervisor.collector = None
            _write_monitor_log(data_dir, "monitor stopped")
        finally:
            pid_file.unlink(missing_ok=True)
            exit_signal.unlink(missing_ok=True)
    finally:
        lock.close()


def install_startup_task(repository: Path, pythonw: str | None = None, data_dir: Path | None = None) -> str:
    if os.name != "nt":
        raise RuntimeError("登录启动项目前仅支持 Windows。")
    from .app import default_data_dir, external_path
    executable = pythonw or str(Path(sys.executable).with_name("pythonw.exe"))
    data = external_path(data_dir or default_data_dir())
    data.mkdir(parents=True, exist_ok=True)
    _stop_running_monitor(data)
    entrypoint = repository / "tools" / "desktop_monitor.py"
    arguments = subprocess.list2cmdline([str(entrypoint), "--data-dir", str(data)])
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$service = New-Object -ComObject Schedule.Service; $service.Connect()",
        "$folder = $service.GetFolder('\\')",
        "$task = $service.NewTask(0)",
        "$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$task.Principal.UserId = $user; $task.Principal.LogonType = 3; $task.Principal.RunLevel = 0",
        "$trigger = $task.Triggers.Create(9); $trigger.UserId = $user",
        "$task.Settings.Hidden = $true; $task.Settings.ExecutionTimeLimit = 'PT0S'",
        "$task.Settings.DisallowStartIfOnBatteries = $false; $task.Settings.StopIfGoingOnBatteries = $false",
        "$task.Settings.RestartCount = 3; $task.Settings.RestartInterval = 'PT1M'",
        "$action = $task.Actions.Create(0)",
        "$action.Path = " + quote(executable),
        "$action.Arguments = " + quote(arguments),
        "$action.WorkingDirectory = " + quote(repository),
        "$registered = $folder.RegisterTaskDefinition(" + quote(TASK_NAME) + ", $task, 6, $null, $null, 3)",
        "$deadline = [DateTime]::UtcNow.AddSeconds(5)",
        "while ($registered.State -eq 4 -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }",
        "if ($registered.State -ne 4) { $null = $registered.Run($null) }",
    ])
    completed = _run_powershell(script)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "创建 Startup 快捷方式失败。")
    startup_shortcut_path().unlink(missing_ok=True)
    return TASK_NAME


def uninstall_startup_task(data_dir: Path | None = None) -> bool:
    if os.name != "nt":
        raise RuntimeError("登录启动项目前仅支持 Windows。")
    shortcut = startup_shortcut_path()
    existed = shortcut.exists()
    from .app import default_data_dir
    _stop_running_monitor(data_dir or default_data_dir())
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$service = New-Object -ComObject Schedule.Service; $service.Connect()",
        "$folder = $service.GetFolder('\\')",
        "$task = @($folder.GetTasks(1) | Where-Object Name -eq '" + TASK_NAME + "')",
        "if ($task.Count) { $folder.DeleteTask('" + TASK_NAME + "', 0); Write-Output 'removed' }",
    ])
    result = _run_powershell(script)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "删除登录监视器任务失败。")
    shortcut.unlink(missing_ok=True)
    return existed or "removed" in result.stdout


def _stop_running_monitor(data_dir: Path) -> None:
    pid_file = data_dir / "desktop-monitor.pid"
    if not pid_file.exists():
        return
    import msvcrt
    lock_path = data_dir / "desktop-monitor.lock"
    if lock_path.exists():
        with lock_path.open("r+b") as lock:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                pass
            else:
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                pid_file.unlink(missing_ok=True)
                return
    (data_dir / "desktop-monitor.exit").touch()
    deadline = time.monotonic() + 35
    while pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.25)
    if pid_file.exists():
        raise TimeoutError("桌面监视器未能在期限内停止；采集服务可能仍在运行。")


def wait_for_stop_file(path: Path, shutdown: Callable[[], None]) -> None:
    while not path.exists():
        time.sleep(0.25)
    shutdown()

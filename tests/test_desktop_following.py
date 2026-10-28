from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil
import sys
import time

from prompt_journal import desktop
from prompt_journal.app import default_data_dir
from prompt_journal.desktop import DesktopSupervisor, is_desktop_main_process, startup_task_action


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.stopped = False

    def poll(self):
        return self.returncode


class DesktopFollowingAcceptance(unittest.TestCase):
    def test_external_shell_finds_existing_packaged_database(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(desktop.os.environ, {"LOCALAPPDATA": temp}):
            packaged = Path(temp) / "Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/data"
            packaged.mkdir(parents=True)
            (packaged / "journal.sqlite3").touch()
            self.assertEqual(default_data_dir(), packaged.resolve())

    def test_distinct_default_databases_require_an_explicit_choice(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(desktop.os.environ, {"LOCALAPPDATA": temp}):
            for folder in ("LocalPromptJournal/data", "Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/LocalPromptJournal/data"):
                path = Path(temp) / folder
                path.mkdir(parents=True)
                (path / "journal.sqlite3").touch()
            with self.assertRaisesRegex(ValueError, "--data-dir"):
                default_data_dir()

    def test_supervisor_starts_for_existing_and_new_desktop_process_then_stops_on_exit(self):
        app_running = True
        starts = []
        stops = []

        def start():
            child = FakeProcess()
            starts.append(child)
            return child

        supervisor = DesktopSupervisor(lambda: app_running, start, lambda child: stops.append(child))
        supervisor.step()
        supervisor.step()
        self.assertEqual(len(starts), 1)
        self.assertEqual(stops, [])

        app_running = False
        supervisor.step()
        self.assertEqual(stops, [starts[0]])

        app_running = True
        supervisor.step()
        self.assertEqual(len(starts), 2)

    def test_supervisor_restarts_collector_after_unexpected_exit_while_app_is_running(self):
        children = []

        def start():
            child = FakeProcess()
            children.append(child)
            return child

        supervisor = DesktopSupervisor(lambda: True, start, lambda child: None)
        supervisor.step()
        children[0].returncode = 1
        supervisor.step()
        self.assertEqual(len(children), 2)

    def test_renderer_child_does_not_count_as_the_desktop_main_process(self):
        executable = Path(r"C:\Program Files\WindowsApps\ChatGPT.exe")
        renderer = {"ExecutablePath": str(executable), "CommandLine": '"ChatGPT.exe" --type=renderer'}
        main = {"ExecutablePath": str(executable), "CommandLine": '"ChatGPT.exe"'}
        self.assertFalse(is_desktop_main_process(renderer, executable))
        self.assertTrue(is_desktop_main_process(main, executable))

    def test_desktop_executable_resolves_from_local_appx_package_without_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "OpenAI.Codex_version"
            executable = package / "app" / "ChatGPT.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()
            repository_key = object()
            package_key = object()
            with patch.object(desktop.winreg, "OpenKey", side_effect=[repository_key, package_key]), \
                 patch.object(desktop.winreg, "EnumKey", side_effect=[package.name, OSError]), \
                 patch.object(desktop.winreg, "QueryValueEx", return_value=(str(package), 0)), \
                 patch.object(desktop.winreg, "CloseKey"):
                self.assertEqual(desktop.resolve_desktop_executable(), executable.resolve())

    def test_install_uses_independent_hidden_logon_task_with_explicit_database(self):
        with tempfile.TemporaryDirectory() as temp:
            shortcut = Path(temp) / desktop.SHORTCUT_NAME
            shortcut.touch()
            completed = desktop.subprocess.CompletedProcess([], 0, "", "")
            with patch.object(desktop, "startup_shortcut_path", return_value=shortcut), \
                 patch.object(desktop, "_run_powershell", return_value=completed) as run, \
                 patch.object(desktop, "_stop_running_monitor"), \
                 patch.object(desktop.subprocess, "Popen") as popen:
                desktop.install_startup_task(Path(r"D:\journal"), r"C:\Python\pythonw.exe", Path(temp) / "data")
                self.assertFalse(shortcut.exists())
                popen.assert_not_called()
        script = run.call_args.args[0]
        self.assertIn("Triggers.Create(9)", script)
        self.assertIn("Hidden = $true", script)
        self.assertIn("--data-dir", script)
        self.assertIn("RegisterTaskDefinition", script)
        self.assertIn("RestartCount = 3", script)

    def test_startup_task_action_runs_hidden_monitor_from_repository_entrypoint(self):
        action = startup_task_action(r"C:\Python\pythonw.exe", r"D:\AI\日志项目")
        self.assertIn('pythonw.exe', action.lower())
        self.assertIn('desktop_monitor.py', action)
        self.assertNotIn('run --start-from-now', action)

    def test_install_registers_logon_task_and_starts_monitor_now(self):
        with tempfile.TemporaryDirectory() as temp:
            shortcut = Path(temp) / desktop.SHORTCUT_NAME
            shortcut.touch()
            completed = desktop.subprocess.CompletedProcess([], 0, "", "")
            with patch.object(desktop, "startup_shortcut_path", return_value=shortcut), \
                 patch.object(desktop, "_run_powershell", return_value=completed) as run, \
                 patch.object(desktop, "_stop_running_monitor"):
                result = desktop.install_startup_task(Path(r"D:\journal"), r"C:\Python\pythonw.exe", Path(temp) / "data")
        self.assertEqual(desktop.TASK_NAME, result)
        script = run.call_args.args[0]
        self.assertIn("$action.Path", script)
        self.assertIn("pythonw.exe", script.lower())
        self.assertIn("$action.WorkingDirectory", script)
        self.assertIn("$registered.Run", script)
        self.assertIn("desktop_monitor.py", script)

    def test_uninstall_is_idempotent_and_removes_existing_user_task(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(desktop.os.environ, {"APPDATA": temp}):
            shortcut = desktop.startup_shortcut_path()
            shortcut.parent.mkdir(parents=True)
            shortcut.touch()
            with patch.object(desktop, "_stop_running_monitor") as stop, \
                 patch.object(desktop, "_run_powershell", return_value=desktop.subprocess.CompletedProcess([], 0, "removed", "")):
                self.assertTrue(desktop.uninstall_startup_task())
                self.assertFalse(shortcut.exists())
                stop.assert_called_once()
            with patch.object(desktop, "_stop_running_monitor") as stop, \
                 patch.object(desktop, "_run_powershell", return_value=desktop.subprocess.CompletedProcess([], 0, "", "")):
                self.assertFalse(desktop.uninstall_startup_task())
                stop.assert_called_once()

    def test_uninstall_without_task_still_stops_a_running_monitor(self):
        with patch.object(desktop, "startup_shortcut_path", return_value=Path("missing-startup-shortcut")), \
             patch.object(desktop, "_stop_running_monitor") as stop, \
             patch.object(desktop, "_run_powershell", return_value=desktop.subprocess.CompletedProcess([], 0, "", "")):
            self.assertFalse(desktop.uninstall_startup_task())
        stop.assert_called_once()

    def test_native_detection_rejects_an_orphan_helper_at_the_same_executable_path(self):
        # A copied command interpreter gives us real long-lived Windows processes
        # at a unique executable path without stopping the user's desktop.
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "ChatGPT.exe"
            shutil.copyfile(Path(desktop.os.environ["SystemRoot"]) / "System32/cmd.exe", executable)
            for marker, expected in (("rem --type=renderer", False), ("rem main-process", True)):
                child = desktop.subprocess.Popen([str(executable), "/d", "/q", "/k", marker],
                    stdin=desktop.subprocess.PIPE, stdout=desktop.subprocess.DEVNULL,
                    stderr=desktop.subprocess.DEVNULL, creationflags=desktop.subprocess.CREATE_NO_WINDOW)
                try:
                    time.sleep(0.1)
                    self.assertIsNone(child.poll())
                    self.assertEqual(desktop.desktop_is_running(executable), expected)
                finally:
                    child.terminate()
                    child.wait(timeout=5)
                    if child.stdin:
                        child.stdin.close()

    def test_monitor_command_honors_an_explicit_data_directory(self):
        from prompt_journal.__main__ import main
        with tempfile.TemporaryDirectory() as temp, patch.object(desktop, "run_monitor") as monitor:
            self.assertEqual(main(["--data-dir", temp, "monitor"]), 0)
            self.assertEqual(monitor.call_args.args[1], Path(temp))


if __name__ == "__main__":
    unittest.main()

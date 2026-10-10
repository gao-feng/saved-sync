"""Cross-platform locking and Windows launcher regression checks."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import sync_common
import browser_session
import windows_launcher


class WindowsSupportTests(unittest.TestCase):
    def test_process_exit_releases_lock(self):
        with tempfile.TemporaryDirectory() as root:
            script = (
                "import sys; from pathlib import Path; import sync_common; "
                "lock=sync_common.SyncLock('xiaohongshu', Path(sys.argv[1])).acquire(); "
                "print('locked', flush=True); sys.stdin.readline()"
            )
            process = subprocess.Popen([sys.executable, "-u", "-c", script, root],
                                       cwd=SCRIPTS, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), "locked")
                with self.assertRaises(sync_common.SyncBusyError):
                    sync_common.SyncLock("xiaohongshu", Path(root)).acquire()
                process.terminate()
                process.wait(timeout=10)
                with sync_common.SyncLock("xiaohongshu", Path(root)):
                    pass
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_reserved_names(self):
        for name in ("CON", "aux.txt", "LPT1", "NUL"):
            self.assertTrue(sync_common.safe_title(name).startswith("_"))
            self.assertTrue(sync_common.safe_directory_name(name).startswith("_"))
            self.assertTrue(browser_session.safe_filename(name).startswith("_"))

    @unittest.skipUnless(os.name == "nt", "Windows browser paths")
    def test_browser_installation_discovery(self):
        with tempfile.TemporaryDirectory() as root:
            executable = Path(root) / "Microsoft/Edge/Application/msedge.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with mock.patch.dict(os.environ, {"PROGRAMFILES": root}):
                self.assertEqual(browser_session.find_browser(), str(executable))

    def test_launcher_preserves_unicode_and_spaces(self):
        env = {"INS2ANKI_OUTPUT": "D:/我的收藏/英语 帖子", "INS2ANKI_FOLDER": "英语 收藏",
               "INS2ANKI_BROWSER": "C:/Program Files/浏览器/chrome.exe"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(sys, "argv", ["launcher", "xiaohongshu"]), \
             mock.patch.object(windows_launcher.os, "chdir"), \
             mock.patch.object(windows_launcher.subprocess, "call", return_value=0) as call:
            self.assertEqual(windows_launcher.main(), 0)
        args = call.call_args.args[0]
        self.assertIn(env["INS2ANKI_OUTPUT"], args)
        self.assertIn(env["INS2ANKI_FOLDER"], args)
        self.assertIn(env["INS2ANKI_BROWSER"], args)

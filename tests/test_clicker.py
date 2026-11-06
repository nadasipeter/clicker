import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

import clicker


class ArgumentsTest(unittest.TestCase):
    def test_invalid_intervals(self):
        for value in ("0", "-1", "nan", "inf", "abc"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                clicker.positive_interval(value)
        self.assertEqual(clicker.positive_interval("2.5"), 2.5)

    def test_invalid_urls(self):
        for value in ("example.com", "file:///tmp/test", "https://", "https://["):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                clicker.site_url(value)

    def test_mac_edge_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            edge = root / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
            edge.parent.mkdir(parents=True)
            edge.touch()
            with patch.object(Path, "home", return_value=root):
                self.assertEqual(clicker.find_browser(), str(edge))


class ProfileTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.source = self.home / "Library/Application Support/Google/Chrome"
        (self.source / "Profile 1").mkdir(parents=True)
        (self.source / "Local State").write_text(json.dumps({
            "profile": {"info_cache": {"Profile 1": {"name": "Personal"}}}
        }))
        (self.source / "Profile 1/Preferences").write_text("original")
        for target, value in (("clicker.sys.platform", "darwin"), ("clicker.Path.home", self.home)):
            mock = patch(target, return_value=value) if target.endswith("home") else patch(target, value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_copy_is_persistent_and_source_is_unchanged(self):
        with patch("builtins.input", return_value="yes") as prompt:
            destination, directory = clicker.prepare_profile("Google Chrome", "Personal")
        self.assertIn("quit ALL Chrome and Edge", prompt.call_args.args[0])
        self.assertEqual(directory, "Profile 1")
        copied = destination / directory / "Preferences"
        self.assertEqual(copied.read_text(), "original")
        copied.write_text("automation changes")
        with patch("builtins.input", return_value="yes"):
            self.assertEqual(clicker.prepare_profile("Google Chrome", "Personal"), (destination, directory))
        self.assertEqual(copied.read_text(), "automation changes")
        self.assertEqual((self.source / directory / "Preferences").read_text(), "original")

    def test_cancel_and_missing_name_create_no_copy(self):
        with patch("builtins.input", return_value="no"), self.assertRaisesRegex(RuntimeError, "Cancelled"):
            clicker.prepare_profile("Google Chrome", "Personal")
        with patch("builtins.input") as prompt, self.assertRaisesRegex(RuntimeError, "found 0"):
            clicker.prepare_profile("Google Chrome", "Missing")
        prompt.assert_not_called()
        self.assertFalse((self.home / "Library/Application Support/Clicker").exists())


class BrowserTest(unittest.TestCase):
    def test_repeated_clicks_relocate_button_and_respect_interval(self):
        import time
        real_sleep = time.sleep

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=clicker.find_browser(), headless=True)
            page = browser.new_page()
            page.set_content('''
                <button onclick="other++">Other</button>
                <div id="target"></div>
                <script>
                window.clicks = []; window.other = 0;
                function render() {
                  const b = document.createElement('button');
                  b.textContent = 'Click me';
                  b.onclick = () => { clicks.push(performance.now()); render(); };
                  document.querySelector('#target').replaceChildren(b);
                }
                render();
                </script>
            ''')
            sleeps = 0

            def stop_after_three(seconds):
                nonlocal sleeps
                sleeps += 1
                if sleeps == 3:
                    raise KeyboardInterrupt
                real_sleep(seconds)

            with patch.object(clicker.time, "sleep", side_effect=stop_after_three):
                with self.assertRaises(KeyboardInterrupt):
                    clicker.click_repeatedly(page, "Click me", 0.2)
            timestamps = page.evaluate("clicks")
            self.assertEqual(len(timestamps), 3)
            self.assertEqual(page.evaluate("other"), 0)
            for before, after in zip(timestamps, timestamps[1:]):
                self.assertGreaterEqual(after - before, 170)
            browser.close()


if __name__ == "__main__":
    unittest.main()

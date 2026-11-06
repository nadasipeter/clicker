import argparse
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


class NativeTest(unittest.TestCase):
    def test_native_open_uses_normal_browser_and_pins_tab(self):
        with patch("clicker.subprocess.run") as launch, patch("builtins.input", return_value="") as prompt, patch(
            "clicker.run_applescript", side_effect=["42, 7", "clicked", "closed"]
        ) as script, patch("clicker.time.sleep"):
            clicker.run_native("Microsoft Edge", "https://example.com", 'Say "Hi"', 1, "Personal")
        launch.assert_called_once_with(["open", "-a", "Microsoft Edge", "https://example.com"], check=True)
        self.assertIn("Personal", prompt.call_args.args[0])
        self.assertEqual(script.call_args.args[1:3], ("42", "7"))

    def test_native_main_bypasses_profile_file_access(self):
        with patch("clicker.sys.platform", "darwin"), patch("clicker.find_browser", return_value="Microsoft Edge"), patch(
            "clicker.Path.read_text"
        ) as prepare, patch("clicker.run_native") as native:
            self.assertEqual(clicker.main(["https://example.com", "Refresh", "1", "--browser", "edge", "--profile", "Personal"]), 0)
        prepare.assert_not_called()
        native.assert_called_once_with("Microsoft Edge", "https://example.com", "Refresh", 1, "Personal")


class BrowserTest(unittest.TestCase):
    def test_repeated_clicks_relocate_button_and_respect_interval(self):
        import time
        real_sleep = time.sleep

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=clicker.find_browser(), headless=True)
            page = browser.new_page()
            page.set_content('<button onclick="this.textContent=\'Done\'">Say &quot;Hi&quot;</button>')
            self.assertEqual(page.evaluate(clicker.native_click_script('Say "Hi"')), "clicked")
            self.assertEqual(page.get_by_role("button").inner_text(), "Done")
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

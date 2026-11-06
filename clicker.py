"""Click a browser button repeatedly by its accessible label."""

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

from playwright.sync_api import Error, sync_playwright


def positive_interval(value):
    try:
        interval = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("interval must be a number of seconds")
    if not math.isfinite(interval) or interval <= 0:
        raise argparse.ArgumentTypeError("interval must be finite and greater than zero")
    return interval


def site_url(value):
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme in ("http", "https") and parsed.hostname
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("site URL must start with http:// or https:// and include a host")
    return value


def find_browser(browser_name=None):
    """Prefer Chrome, then Edge; check system and per-user macOS installs."""
    for app, binary in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge")):
        if browser_name and browser_name not in app.lower():
            continue
        for root in (Path("/Applications"), Path.home() / "Applications"):
            candidate = root / f"{app}.app" / "Contents" / "MacOS" / binary
            if candidate.is_file():
                return str(candidate)
    # Also allow developing and running the same application on Linux/Windows.
    for name in ("google-chrome", "google-chrome-stable", "microsoft-edge", "msedge", "chromium", "chromium-browser"):
        if browser_name and browser_name not in name:
            continue
        candidate = shutil.which(name)
        if candidate:
            return candidate
    raise RuntimeError("No supported browser found. Install Google Chrome or Microsoft Edge in /Applications.")


def click_repeatedly(page, label, interval):
    # A locator is resolved again on every click, including after page updates.
    button = page.get_by_role("button", name=label, exact=True)
    count = 0
    while not page.is_closed():
        button.click(timeout=30_000)
        count += 1
        print(f"Clicked {label!r} ({count})", flush=True)
        # Slow page actions never cause a burst of catch-up clicks.
        time.sleep(interval)


def native_click_script(label):
    # JSON encoding keeps labels out of executable JavaScript syntax.
    return """(() => {
      const normalize = s => s.replace(/\\s+/g, ' ').trim();
      const label = normalize(LABEL);
      const buttons = [...document.querySelectorAll('button, input[type="button"], input[type="submit"], [role="button"]')]
        .filter(b => b.getClientRects().length && getComputedStyle(b).visibility !== 'hidden')
        .filter(b => {
          const ids = (b.getAttribute('aria-labelledby') || '').split(/\\s+/).filter(Boolean);
          const referenced = ids.map(id => document.getElementById(id)?.textContent || '').join(' ');
          return normalize(referenced || b.getAttribute('aria-label') || b.value || b.textContent || '') === label;
        });
      if (buttons.length > 1) return 'ambiguous';
      if (!buttons.length || buttons[0].disabled || buttons[0].getAttribute('aria-disabled') === 'true') return 'waiting';
      buttons[0].click(); return 'clicked';
    })()""".replace("LABEL", json.dumps(label))


def run_applescript(script, *arguments):
    result = subprocess.run(["osascript", "-e", script, "--", *arguments],
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(
            "Browser scripting failed. Enable View > Developer > Allow JavaScript "
            "from Apple Events in the browser, and allow Terminal to control it "
            "in macOS Privacy & Security > Automation. " + result.stderr.strip()
        )
    return result.stdout.strip()


def run_native(executable, url, label, interval, profile_name=None):
    app = "Microsoft Edge" if "edge" in executable.lower() else "Google Chrome"
    # LaunchServices opens the regular browser, preserving its own profile handling.
    subprocess.run(["open", "-a", app, url], check=True)
    selection = f" Switch to your {profile_name!r} profile and open the target URL there." if profile_name else ""
    try:
        input(f"{app} opened normally.{selection}\n"
              f"Make {url} the active tab in the correct profile, then press Enter. "
              "Ctrl+C cancels: ")
    except EOFError as exc:
        raise RuntimeError("Native mode requires an interactive terminal to confirm the target tab.") from exc
    # App names are fixed constants; user-supplied JavaScript is passed as argv.
    target = run_applescript(f'tell application "{app}" to return {{id of front window, id of active tab of front window}}')
    window_id, tab_id = [str(int(part.strip())) for part in target.split(",")]
    script = f'''on run argv
      tell application "{app}"
        repeat with w in windows
          if (id of w as text) is item 1 of argv then
            repeat with t in tabs of w
              if (id of t as text) is item 2 of argv then
                return execute t javascript (item 3 of argv)
              end if
            end repeat
          end if
        end repeat
      end tell
      return "closed"
    end run'''
    count = 0
    deadline = time.monotonic() + 30
    while True:
        result = run_applescript(script, window_id, tab_id, native_click_script(label))
        if result == "closed":
            return
        if result == "ambiguous":
            raise RuntimeError("Multiple buttons match the label; use a unique label.")
        if result == "clicked":
            count += 1
            print(f"Clicked {label!r} ({count})", flush=True)
            time.sleep(interval)
            deadline = time.monotonic() + 30
        elif result == "waiting" and time.monotonic() < deadline:
            time.sleep(0.25)
        else:
            raise RuntimeError("The target button was not ready within 30 seconds.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open a site and repeatedly click a button. Press Ctrl+C to stop.")
    parser.add_argument("site_url", type=site_url)
    parser.add_argument("button_label", help="Exact accessible button name (usually its visible text)")
    parser.add_argument("interval", type=positive_interval, help="Seconds between clicks, e.g. 1 or 2.5")
    parser.add_argument("--profile", help="Profile display name; macOS native mode asks you to select it in the browser")
    parser.add_argument("--browser", choices=("chrome", "edge"), help="Choose Chrome or Edge (default: first installed)")
    args = parser.parse_args(argv)
    if not args.button_label.strip():
        parser.error("button label must not be empty")
    try:
        executable = find_browser(args.browser)
        if sys.platform == "darwin":
            run_native(executable, args.site_url, args.button_label, args.interval, args.profile)
            return 0
        if args.profile:
            raise RuntimeError("Named profiles are supported on macOS only.")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, headless=False)
            try:
                page = browser.new_page()
                page.goto(args.site_url, wait_until="domcontentloaded")
                print("Waiting for the button. Press Ctrl+C to stop.", flush=True)
                click_repeatedly(page, args.button_label, args.interval)
            finally:
                browser.close()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except (Error, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

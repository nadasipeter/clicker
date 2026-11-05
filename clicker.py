"""Click a browser button repeatedly by its accessible label."""

import argparse
import math
from pathlib import Path
import shutil
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


def find_browser():
    """Prefer Chrome, then Edge; check system and per-user macOS installs."""
    for app, binary in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge")):
        for root in (Path("/Applications"), Path.home() / "Applications"):
            candidate = root / f"{app}.app" / "Contents" / "MacOS" / binary
            if candidate.is_file():
                return str(candidate)
    # Also allow developing and running the same application on Linux/Windows.
    for name in ("google-chrome", "google-chrome-stable", "microsoft-edge", "msedge", "chromium", "chromium-browser"):
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open a site and repeatedly click a button. Press Ctrl+C to stop.")
    parser.add_argument("site_url", type=site_url)
    parser.add_argument("button_label", help="Exact accessible button name (usually its visible text)")
    parser.add_argument("interval", type=positive_interval, help="Seconds between clicks, e.g. 1 or 2.5")
    args = parser.parse_args(argv)
    if not args.button_label.strip():
        parser.error("button label must not be empty")
    try:
        executable = find_browser()
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
    except (Error, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

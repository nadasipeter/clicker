"""Click a browser button repeatedly by its accessible label."""

import argparse
import json
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


def read_profile_names(source, brand):
    state_path = source / "Local State"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{brand.title()} profile data was not found at {state_path}. "
            "For Edge use --browser edge. In the selected browser open "
            "edge://version or chrome://version and check Profile Path."
        ) from exc
    except PermissionError as exc:
        raise RuntimeError(f"Permission denied reading {state_path}. Check macOS file permissions.") from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Cannot read valid profile metadata from {state_path} ({type(exc).__name__}).") from exc
    if not isinstance(state, dict):
        raise RuntimeError(f"Invalid profile metadata format in {state_path}.")
    profile = state.get("profile", {})
    cache = profile.get("info_cache", {}) if isinstance(profile, dict) else {}
    names = {directory: info["name"] for directory, info in cache.items()
             if isinstance(info, dict) and isinstance(info.get("name"), str)} if isinstance(cache, dict) else {}
    # Some browser versions omit the shared cache but retain names in Preferences.
    for candidate in source.iterdir():
        if candidate.name != "Default" and not candidate.name.startswith("Profile "):
            continue
        if candidate.name in names or not candidate.is_dir():
            continue
        try:
            preferences = json.loads((candidate / "Preferences").read_text(encoding="utf-8"))
            name = preferences["profile"]["name"]
            if isinstance(name, str):
                names[candidate.name] = name
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return names


def prepare_profile(executable, name):
    """Resolve a macOS display name and seed a separate persistent data directory."""
    if sys.platform != "darwin":
        raise RuntimeError("Named profile selection currently supports macOS only.")
    brand = "edge" if "edge" in executable.lower() else "chrome"
    support = Path.home() / "Library" / "Application Support"
    source = support / ("Microsoft Edge" if brand == "edge" else "Google/Chrome")
    profiles = read_profile_names(source, brand)
    matches = [directory for directory, display_name in profiles.items() if display_name == name]
    if len(matches) != 1:
        available = ", ".join(repr(value) for value in profiles.values()) or "none"
        raise RuntimeError(f"Expected one {brand.title()} profile named {name!r}; found {len(matches)}. "
                           f"Available profiles: {available}. Use --browser edge for Edge profiles.")
    directory = matches[0]
    if Path(directory).name != directory or directory in (".", ".."):
        raise RuntimeError("Invalid browser profile directory.")
    if not (source / directory).is_dir():
        raise RuntimeError("The selected browser profile directory is missing.")
    try:
        response = input(
            "Save your work and quit ALL Chrome and Edge instances (Cmd+Q), "
            "including background instances.\n"
            "The app will use a separate persistent copy of the selected profile; "
            "you may need to sign in again.\n"
            "Type yes when all instances are closed, or anything else to cancel: "
        )
    except EOFError as exc:
        raise RuntimeError("Profile mode requires confirmation in an interactive terminal.") from exc
    if response.strip().lower() != "yes":
        raise RuntimeError("Cancelled; no browser was opened.")
    destination = support / "Clicker" / brand / directory
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        staging = destination.with_name(directory + ".initializing")
        if staging.exists():
            raise RuntimeError(f"An incomplete profile copy exists at {staging}. Remove it before retrying.")
        try:
            staging.mkdir(mode=0o700)
            shutil.copy2(source / "Local State", staging / "Local State")
            shutil.copytree(source / directory, staging / directory,
                            ignore=shutil.ignore_patterns("Singleton*", "Cache", "Code Cache", "GPUCache"))
            staging.rename(destination)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return destination, directory


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
    parser.add_argument("--profile", help="Exact macOS browser profile display name; uses a persistent automation copy")
    parser.add_argument("--browser", choices=("chrome", "edge"), help="Choose Chrome or Edge (default: first installed)")
    args = parser.parse_args(argv)
    if not args.button_label.strip():
        parser.error("button label must not be empty")
    try:
        executable = find_browser(args.browser)
        profile = prepare_profile(executable, args.profile) if args.profile else None
        with sync_playwright() as playwright:
            if profile:
                data_directory, profile_directory = profile
                browser = playwright.chromium.launch_persistent_context(
                    str(data_directory), executable_path=executable, headless=False,
                    args=[f"--profile-directory={profile_directory}"],
                )
            else:
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
    except (Error, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

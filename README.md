# Browser button clicker

Python CLI that opens a site and clicks a button repeatedly. Requires Python 3.10+
and Google Chrome or Microsoft Edge. On macOS, install the browser in
`/Applications` or `~/Applications`; Chrome is preferred when both are installed.

## Install (macOS)

### 1. Install Python

1. Open the official [Python downloads for macOS](https://www.python.org/downloads/macos/)
   and download a stable Python 3 installer (Python 3.10 or newer).
2. Open the downloaded `.pkg` file and follow the installation steps. The
   universal2 installer supports both Apple Silicon and Intel Macs.
3. Open a new **Terminal** window (Applications → Utilities → Terminal) and check:

   ```sh
   python3 --version
   python3 -m pip --version
   ```

   The Python version should be 3.10 or newer. If `python3` is not found, close
   and reopen Terminal after completing the installer.

If you already use [Homebrew](https://brew.sh/), you can install Python with
`brew install python` instead, then run the version checks above.

If you encounter certificate verification errors with the python.org installation,
run `Install Certificates.command` from its versioned Python folder in
`/Applications`, then retry the failed command.

### 2. Install the app dependencies

Download or clone this repository, then open Terminal in its directory. For
example, if you downloaded it to `~/Downloads/clicker-main`:

```sh
cd ~/Downloads/clicker-main
```

Create and activate a virtual environment, then install the dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No browser driver or Playwright browser download is required: the app uses your
installed browser.

In each new Terminal window, return to the repository directory and run
`source .venv/bin/activate` before using the commands below.

## Run

```sh
python clicker.py "https://example.com" "Refresh" 1
```

The three positional parameters are the site URL, button label, and interval in
seconds. Decimal intervals such as `2.5` work. The first click happens as soon as
the button is ready; the app waits the requested interval after each completed
click before clicking again. Page delays can make clicks farther apart. Press **Ctrl+C** in the
terminal to stop and close the browser.

The label matches the exact accessible name of a button (including HTML buttons,
submit inputs, and elements with `role="button"`). It must identify one button
in the main page. Duplicate names produce an error instead of clicking an
arbitrary button. Frames and links are not searched. Each click waits up to 30
seconds for the button to become actionable, then reports an error if it cannot.

The browser opens a separate temporary session; existing browser logins are not
shared. You can log in manually in the opened window before the button wait
expires. Closing the window also stops clicking.

## Use a named profile (macOS)

```sh
python clicker.py "https://example.com" "Refresh" 1 --browser chrome --profile "Personal"
python clicker.py "https://example.com" "Refresh" 1 --browser edge --profile "Work"
```

Use the exact profile display name shown in the browser's profile settings.
`--browser` selects Chrome or Edge; if omitted, the first installed browser is
used, with Chrome preferred. Without `--profile`, the temporary session described
above is used and there is no close-browser prompt.

Before opening a named profile, the app asks you to save your work and quit all
Chrome and Edge instances with **Cmd+Q**, including background instances. Type
`yes` to continue; any other answer cancels. The app does not force browsers to
quit or independently verify that you closed them.

Chrome restricts automation of its normal data directory. The app therefore
copies the selected profile into a separate data directory on its first use:
`~/Library/Application Support/Clicker/<chrome-or-edge>/<profile-directory>`.
Later runs reuse that copy, including logins made in the automation browser.
Changes are not synchronized with your everyday browser. Encrypted cookies,
passwords, and managed settings may not transfer; sign in again if necessary.
The copy contains private browser data, so treat it like your original profile.
Do not run two clickers using the same automation profile simultaneously.

If your profile is in Edge, include `--browser edge`; otherwise Chrome is chosen
when both browsers are installed. The app reads profile names from `Local State`
and falls back to each profile's `Preferences` file when needed. Errors identify
the selected browser and missing or unreadable metadata; a name mismatch lists
the names found. For a missing data directory, open `edge://version` in Edge (or
`chrome://version` in Chrome) and check **Profile Path**. Custom data directories
and Beta/Dev/Canary browser editions are not currently supported.

## Verify

```sh
python -m unittest discover -s tests -v
```

Tests use an installed browser in headless mode and a local page; no external
website or account is required.

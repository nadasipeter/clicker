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

## Verify

```sh
python -m unittest discover -s tests -v
```

Tests use an installed browser in headless mode and a local page; no external
website or account is required.

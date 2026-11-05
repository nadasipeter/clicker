# Browser button clicker

Python CLI that opens a site and clicks a button repeatedly. Requires Python 3.10+
and Google Chrome or Microsoft Edge. On macOS, install the browser in
`/Applications` or `~/Applications`; Chrome is preferred when both are installed.

## Install (macOS)

From this repository directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No browser driver or Playwright browser download is required: the app uses your
installed browser.

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

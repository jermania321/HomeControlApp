
# HomeControlApp

## Gmail Priority Inbox

On Windows, double-click `setup.bat` once to create an isolated `.venv` and
install dependencies (it prefers Python 3.12, then falls back to 3.9), then
double-click `start.bat` to launch the app. You can
also launch it from the project folder with `.venv\Scripts\python.exe -m
homecontrol`. It shows the 100 newest INBOX messages using sender, subject,
date, and Gmail's snippet only (message bodies are never fetched). Click a subject to open that exact Gmail message. **Connect
Gmail** opens OAuth on first use; the only requested scope is
`https://www.googleapis.com/auth/gmail.readonly`. Checks run every 30 minutes by default (configurable from 1 to 1440 minutes) or with
**Check now**. New HIGH alerts use Gmail history checkpoints and persisted
message-ID deduplication; expired history is re-baselined without old alerts.
Closing the window hides it to the system tray; use tray Open or Exit.

Home and Gmail views share the same window. Home displays India and Dallas
local time, plus indicative ECB reference exchange rates from the public
Frankfurter API (one USD-base request for INR and JPY). Rates refresh every six
hours, are cached in settings, and are marked stale after 24 hours. Network
errors do not erase the last successful rates. Time-zone data uses the system
database or the `tzdata` package on Windows.

Use the **Start with Windows** checkbox to launch HomeControlApp after this
Windows user signs in. Enabling it creates the app-specific
`HomeControlApp-start.bat` entry in the current user's Startup folder; disabling
it removes only that entry. The launcher contains the project and virtualenv
paths, not OAuth credentials or tokens. Startup applies at user sign-in (not
before sign-in). `start.bat` launches detached using `pythonw.exe`; startup
failures before the GUI opens are logged to `%APPDATA%\HomeControlApp\app.log`.

Priority rules are editable in **Priority rules** and stored in
`%APPDATA%\HomeControlApp\settings.json` (or `~/HomeControlApp` if APPDATA is
unset). OAuth setup, credentials and token storage details follow below.

## Read-only Gmail integration

The optional `homecontrol.gmail_integration.fetch_latest_inbox()` function uses
Google's official Gmail API and the installed-app OAuth flow. It requests only
`https://www.googleapis.com/auth/gmail.readonly`, reads up to the 100 newest
messages labeled `INBOX`, and returns sender, decoded subject, UTC received
date, snippet preview, and priority from `classify_priority(subject)`. It does
not send, delete, or modify messages. The function is UI-independent and
accepts an API service double for tests.

### Google Cloud setup

1. Create/select a project in Google Cloud Console and enable the **Gmail API**.
2. Configure the OAuth consent screen for the intended audience and add the
   Gmail read-only scope above. For external/testing apps, add authorized test
   users as required by Google's consent-screen configuration.
3. Create an OAuth client ID with application type **Desktop app** and download
   its JSON file.
4. Place that file outside the repository at
   `%APPDATA%\HomeControlApp\credentials.json` (normally
   `C:\Users\<you>\AppData\Roaming\HomeControlApp\credentials.json`). The
   integration writes the refresh/access token to
   `%APPDATA%\HomeControlApp\gmail-token.json`. Both files contain sensitive
   authorization material; do not commit, share, or expose them.
5. Install dependencies from `requirements.txt`, then launch `python -m
   homecontrol` and select **Connect Gmail**. Subsequent sessions refresh the
   saved authorization when possible.

The token file is sensitive. On Windows, protection at rest depends on the
user-specific ACLs applied to the `%APPDATA%` directory by the operating system
and local account configuration; the integration does not add a separate
encryption layer. Restrict access to the account and do not place the file in a
shared or synchronized location.

An alternate credentials or token path can be passed to `fetch_latest_inbox`
for controlled deployments/tests. Authentication and API failures are raised
as `GmailIntegrationError` with sanitized messages.

### Tests

Run `python -m unittest`. Gmail API calls are mocked; the tests require no live
Google account, credentials, or network access.

Application modules are grouped under `homecontrol/`, with tests under `tests/`.
See `SKILLS.md` for the file-organization rules to follow when adding modules.

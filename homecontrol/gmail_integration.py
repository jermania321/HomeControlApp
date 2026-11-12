"""Read-only Gmail inbox integration with installed-app OAuth."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from email.header import decode_header, make_header
from pathlib import Path

from .priority_classifier import classify_priority

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_MESSAGES = 100


class GmailIntegrationError(RuntimeError):
    """A safe, user-displayable Gmail integration error."""


def _credential_paths():
    """Return external config/token paths; neither is stored in the repository."""
    root = Path(os.environ.get("APPDATA", Path.home())) / "HomeControlApp"
    return root / "credentials.json", root / "gmail-token.json"


def _credentials(credentials_path=None, token_path=None):
    configured, saved = _credential_paths()
    client_file = Path(credentials_path) if credentials_path else configured
    token_file = Path(token_path) if token_path else saved
    creds = None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        if token_file.exists():
            try:
                with token_file.open("r", encoding="utf-8") as token_stream:
                    token_data = json.load(token_stream)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                raise GmailIntegrationError("The saved Gmail authorization has unexpected permissions.")
            if (not isinstance(token_data, dict)
                    or not isinstance(token_data.get("scopes"), list)
                    or token_data["scopes"] != SCOPES):
                raise GmailIntegrationError("The saved Gmail authorization has unexpected permissions.")
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not client_file.is_file():
                raise GmailIntegrationError(
                    "Gmail is not configured. Add an OAuth desktop client credentials file "
                    "at the documented external location."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
            creds = flow.run_local_server(port=0)
        # Prevent storing a broader scope if a stale token file was supplied.
        if set(creds.scopes or ()) != set(SCOPES):
            raise GmailIntegrationError("The saved Gmail authorization has unexpected permissions.")
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds
    except GmailIntegrationError:
        raise
    except Exception as exc:
        raise GmailIntegrationError("Could not authorize read-only access to Gmail.") from exc


def _decode_text(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeError, LookupError, ValueError):
        return value


def _received_date(internal_date):
    try:
        value = int(internal_date) / 1000
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _message_record(message, rules=None):
    headers = {h.get("name", "").casefold(): h.get("value", "")
               for h in message.get("payload", {}).get("headers", [])}
    subject = _decode_text(headers.get("subject", ""))
    return {
        "id": str(message.get("id", "")),
        "sender": _decode_text(headers.get("from", "")),
        "subject": subject,
        "received_date": _received_date(message.get("internalDate")),
        "snippet": message.get("snippet", ""),
        "priority": classify_priority(subject, rules),
    }


def gmail_message_url(message_id):
    """Build a Gmail URL only for a valid opaque message identifier."""
    from urllib.parse import quote
    if not isinstance(message_id, str) or not message_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in message_id):
        return ""
    return "https://mail.google.com/mail/u/0/#all/" + quote(message_id, safe="")


def fetch_latest_inbox(service=None, *, credentials_path=None, token_path=None, rules=None):
    """Return up to 100 newest INBOX messages; accepts a Gmail API test double."""
    try:
        if service is None:
            from googleapiclient.discovery import build

            service = build("gmail", "v1", credentials=_credentials(credentials_path, token_path),
                            cache_discovery=False)
        listed = service.users().messages().list(userId="me", labelIds=["INBOX"],
                                                 maxResults=MAX_MESSAGES).execute()
        records = []
        for item in listed.get("messages", [])[:MAX_MESSAGES]:
            message = service.users().messages().get(userId="me", id=item["id"],
                                                       format="metadata",
                                                       metadataHeaders=["From", "Subject"]).execute()
            records.append(_message_record(message, rules))
            records[-1]["id"] = str(item["id"])
        return records
    except GmailIntegrationError:
        raise
    except Exception as exc:
        raise GmailIntegrationError("Gmail could not be read. Check the connection and try again.") from exc


def connect_gmail(*, credentials_path=None, token_path=None):
    """Perform explicit desktop OAuth and return an authorized Gmail service."""
    try:
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=_credentials(credentials_path, token_path),
                     cache_discovery=False)
    except GmailIntegrationError:
        raise
    except Exception as exc:
        raise GmailIntegrationError("Could not connect to Gmail. Check configuration and try again.") from exc


def poll_new_high(service, state, rules=None):
    """Read history since persisted checkpoint; return newly HIGH message IDs.

    State is mutated only after successful history traversal. An invalid/expired
    checkpoint is re-baselined to current profile history without alerts.
    """
    messages_api = service.users().messages()
    history_api = service.users().history()
    if not state.get("history_id"):
        try:
            profile = service.users().getProfile(userId="me").execute()
        except Exception as exc:
            raise GmailIntegrationError("Gmail could not be checked. Check the connection and try again.") from exc
        state["history_id"] = str(profile["historyId"])
        state["seen_ids"] = list(state.get("seen_ids", []))
        return []
    start = str(state["history_id"])
    try:
        response = history_api.list(userId="me", startHistoryId=start, historyTypes=["messageAdded"]).execute()
    except Exception as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status != 404:
            raise GmailIntegrationError("Gmail could not be checked. Check the connection and try again.") from exc
        try:
            profile = service.users().getProfile(userId="me").execute()
        except Exception as profile_exc:
            raise GmailIntegrationError("Gmail could not be checked. Check the connection and try again.") from profile_exc
        state["history_id"] = str(profile["historyId"])
        return []
    added, newest = set(), start
    while True:
        for row in response.get("history", []):
            newest = max(newest, str(row.get("id", newest)), key=lambda x: int(x))
            for item in row.get("messagesAdded", []):
                msg = item.get("message", {})
                if "INBOX" in msg.get("labelIds", []):
                    added.add(msg.get("id"))
        token = response.get("nextPageToken")
        if not token:
            if response.get("historyId"):
                newest = max(newest, str(response["historyId"]), key=lambda x: int(x))
            break
        try:
            response = history_api.list(userId="me", startHistoryId=start,
                                        historyTypes=["messageAdded"], pageToken=token).execute()
        except Exception as exc:
            raise GmailIntegrationError("Gmail could not be checked. Check the connection and try again.") from exc
    seen = set(state.get("seen_ids", []))
    alerts = []
    for mid in added - seen:
        try:
            message = messages_api.get(userId="me", id=mid, format="metadata", metadataHeaders=["From", "Subject"]).execute()
        except Exception as exc:
            raise GmailIntegrationError("Gmail could not be checked. Check the connection and try again.") from exc
        if _message_record(message, rules)["priority"] == "HIGH":
            alerts.append(mid)
        seen.add(mid)
    # IDs are marked seen regardless of priority, avoiding repeated metadata reads.
    state["seen_ids"] = sorted(seen)
    state["history_id"] = newest
    return alerts

import unittest
import json
import sys
import types
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from gmail_integration import GmailIntegrationError, SCOPES, _message_record, _credentials, fetch_latest_inbox


def make_service(messages):
    service = Mock()
    service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": str(i)} for i in range(len(messages))]
    }
    service.users.return_value.messages.return_value.get.side_effect = [
        Mock(execute=Mock(return_value=m)) for m in messages
    ]
    return service


class GmailIntegrationTests(unittest.TestCase):
    def test_lists_inbox_and_maps_decoded_headers_and_priority(self):
        msg = {"internalDate": "1700000000000", "snippet": "Preview",
               "payload": {"headers": [
                   {"name": "From", "value": "=?utf-8?b?SsO2aG4=?= <j@example.com>"},
                   {"name": "Subject", "value": "=?utf-8?b?VXJnZW50OiBwbGFu?="},
               ]}}
        service = make_service([msg])
        result = fetch_latest_inbox(service)
        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me", labelIds=["INBOX"], maxResults=100)
        self.assertEqual(result[0]["sender"], "Jöhn <j@example.com>")
        self.assertEqual(result[0]["subject"], "Urgent: plan")
        self.assertEqual(result[0]["priority"], "HIGH")
        self.assertEqual(result[0]["snippet"], "Preview")
        self.assertTrue(result[0]["received_date"].startswith("2023-11-14"))
        service.users.return_value.messages.return_value.get.assert_called_once_with(
            userId="me", id="0", format="metadata", metadataHeaders=["From", "Subject"])

    def test_caps_results_at_one_hundred(self):
        service = make_service([{"payload": {"headers": []}} for _ in range(101)])
        self.assertEqual(len(fetch_latest_inbox(service)), 100)

    def test_api_failure_is_sanitized(self):
        service = Mock()
        service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("secret token")
        with self.assertRaisesRegex(GmailIntegrationError, "connection") as caught:
            fetch_latest_inbox(service)
        self.assertNotIn("secret token", str(caught.exception))

    def test_missing_subject_is_low(self):
        self.assertEqual(_message_record({"payload": {"headers": []}})["priority"], "LOW")

    def test_empty_result(self):
        service = make_service([])
        self.assertEqual(fetch_latest_inbox(service), [])
        service.users.return_value.messages.return_value.get.assert_not_called()

    def test_malformed_date_is_empty(self):
        result = _message_record({"internalDate": "not-a-date", "payload": {"headers": []}})
        self.assertEqual(result["received_date"], "")


class OAuthTests(unittest.TestCase):
    def token_json(self, scopes=None):
        return json.dumps({"scopes": SCOPES if scopes is None else scopes})

    def oauth_modules(self, credentials, flow):
        request_module = types.ModuleType("google.auth.transport.requests")
        request_module.Request = Mock(return_value="request")
        credentials_module = types.ModuleType("google.oauth2.credentials")
        credentials_module.Credentials = credentials
        flow_module = types.ModuleType("google_auth_oauthlib.flow")
        flow_module.InstalledAppFlow = flow
        modules = {
            "google": types.ModuleType("google"),
            "google.auth": types.ModuleType("google.auth"),
            "google.auth.transport": types.ModuleType("google.auth.transport"),
            "google.auth.transport.requests": request_module,
            "google.oauth2": types.ModuleType("google.oauth2"),
            "google.oauth2.credentials": credentials_module,
            "google_auth_oauthlib": types.ModuleType("google_auth_oauthlib"),
            "google_auth_oauthlib.flow": flow_module,
        }
        return patch.dict(sys.modules, modules)

    def test_desktop_flow_requests_exact_scope(self):
        creds = Mock(valid=True, scopes=SCOPES, to_json=Mock(return_value="{}"))
        flow = Mock()
        flow.from_client_secrets_file.return_value.run_local_server.return_value = creds
        with TemporaryDirectory() as directory:
            client = Path(directory) / "client.json"
            client.write_text("{}", encoding="utf-8")
            with self.oauth_modules(Mock(), flow):
                self.assertIs(_credentials(client, Path(directory) / "token.json"), creds)
        flow.from_client_secrets_file.assert_called_once_with(str(client), SCOPES)
        flow.from_client_secrets_file.return_value.run_local_server.assert_called_once_with(port=0)

    def test_valid_token_is_reused(self):
        creds = Mock(valid=True, expired=False, scopes=SCOPES, to_json=Mock(return_value="{}"))
        credentials = Mock()
        credentials.from_authorized_user_file.return_value = creds
        flow = Mock()
        with TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            token.write_text(self.token_json(), encoding="utf-8")
            with self.oauth_modules(credentials, flow):
                self.assertIs(_credentials(Path(directory) / "missing.json", token), creds)
        creds.refresh.assert_not_called()
        flow.from_client_secrets_file.assert_not_called()

    def test_expired_token_is_refreshed(self):
        creds = Mock(valid=True, expired=True, refresh_token="refresh", scopes=SCOPES,
                     to_json=Mock(return_value="{}"))
        credentials = Mock()
        credentials.from_authorized_user_file.return_value = creds
        with TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            token.write_text(self.token_json(), encoding="utf-8")
            with self.oauth_modules(credentials, Mock()):
                self.assertIs(_credentials(token_path=token), creds)
        creds.refresh.assert_called_once_with("request")

    def test_refresh_failure_is_sanitized(self):
        creds = Mock(valid=False, expired=True, refresh_token="sensitive", scopes=SCOPES)
        creds.refresh.side_effect = RuntimeError("secret refresh token")
        credentials = Mock()
        credentials.from_authorized_user_file.return_value = creds
        with TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            token.write_text(self.token_json(), encoding="utf-8")
            with self.oauth_modules(credentials, Mock()):
                with self.assertRaises(GmailIntegrationError) as caught:
                    _credentials(token_path=token)
        self.assertNotIn("secret refresh token", str(caught.exception))

    def test_saved_token_with_broader_scope_is_rejected(self):
        creds = Mock(valid=True, expired=False,
                     scopes=SCOPES + ["https://www.googleapis.com/auth/gmail.modify"])
        credentials = Mock()
        credentials.from_authorized_user_file.return_value = creds
        with TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            token.write_text(self.token_json(SCOPES + ["https://www.googleapis.com/auth/gmail.modify"]), encoding="utf-8")
            with self.oauth_modules(credentials, Mock()):
                with self.assertRaisesRegex(GmailIntegrationError, "unexpected permissions"):
                    _credentials(token_path=token)

    def test_persisted_token_with_broader_scope_is_rejected_before_loading(self):
        credentials = Mock()
        with TemporaryDirectory() as directory:
            token = Path(directory) / "token.json"
            token.write_text(self.token_json(["https://www.googleapis.com/auth/gmail.modify"]), encoding="utf-8")
            with self.oauth_modules(credentials, Mock()):
                with self.assertRaisesRegex(GmailIntegrationError, "unexpected permissions"):
                    _credentials(token_path=token)
        credentials.from_authorized_user_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()

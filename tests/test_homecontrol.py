import os
import types
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import Mock, patch

from homecontrol import load_settings, save_settings, save_connection_state, set_start_with_windows
from homecontrol.gmail_integration import poll_new_high, GmailIntegrationError
from homecontrol.priority_classifier import classify_priority, DEFAULT_RULES


class SettingsTests(unittest.TestCase):
    def test_start_with_windows_setting_persists_and_validates(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            data = load_settings()
            self.assertIs(data["start_with_windows"], False)
            data["start_with_windows"] = True
            save_settings(data)
            self.assertIs(load_settings()["start_with_windows"], True)
            save_settings({"start_with_windows": "yes"})
            self.assertIs(load_settings()["start_with_windows"], False)

    def test_startup_script_quotes_project_paths_and_removes_exact_entry(self):
        with TemporaryDirectory(prefix="Home Control ") as directory:
            appdata = Path(directory) / "user appdata"
            project = Path(directory) / "my project"
            set_start_with_windows(True, project, appdata)
            entry = appdata / "Microsoft/Windows/Start Menu/Programs/Startup/HomeControlApp-start.bat"
            script = entry.read_text(encoding="utf-8")
            self.assertIn(f'cd /d "{project.resolve()}"', script)
            self.assertIn(f'"{(project.resolve() / ".venv" / "Scripts" / "pythonw.exe")}" -m homecontrol', script)
            self.assertNotIn("token", script.lower())
            unrelated = entry.parent / "other-app.bat"
            unrelated.write_text("keep", encoding="utf-8")
            set_start_with_windows(False, project, appdata)
            self.assertFalse(entry.exists())
            self.assertTrue(unrelated.exists())

    def test_startup_script_uses_repository_root_by_default(self):
        with TemporaryDirectory() as directory:
            set_start_with_windows(True, appdata=directory)
            entry = Path(directory) / "Microsoft/Windows/Start Menu/Programs/Startup/HomeControlApp-start.bat"
            script = entry.read_text(encoding="utf-8")
            project_root = Path(__file__).resolve().parents[1]
            self.assertIn(f'cd /d "{project_root}"', script)
            self.assertIn(str(project_root / ".venv" / "Scripts" / "pythonw.exe"), script)

    def test_rules_persist_per_user(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            data = load_settings(); data["rules"]["high"] = ["payroll"]
            save_settings(data)
            self.assertEqual(load_settings()["rules"]["high"], ["payroll"])
        self.assertEqual(classify_priority("Payroll notice", {"high": ["payroll"], "medium": []}), "HIGH")

    def test_atomic_save_leaves_valid_settings(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            data = load_settings()
            data["history_id"] = "42"
            save_settings(data)
            self.assertEqual(load_settings()["history_id"], "42")
            self.assertEqual(list((__import__("pathlib").Path(directory) / "HomeControlApp").glob("*.tmp")), [])

    def test_connected_defaults_and_round_trips(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            self.assertIs(load_settings()["connected"], False)
            data = load_settings(); data["connected"] = True
            save_settings(data)
            self.assertIs(load_settings()["connected"], True)

    def test_connected_setting_requires_boolean(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            save_settings({"connected": "yes"})
            self.assertIs(load_settings()["connected"], False)

    def test_non_object_json_returns_defaults(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            settings_file = Path(directory) / "HomeControlApp" / "settings.json"
            settings_file.parent.mkdir(parents=True)
            for invalid_shape in ("[]", "null"):
                with self.subTest(json=invalid_shape):
                    settings_file.write_text(invalid_shape, encoding="utf-8")
                    self.assertEqual(load_settings(), {
                        "rules": {key: list(value) for key, value in DEFAULT_RULES.items()},
                        "history_id": None,
                        "seen_ids": [],
                        "connected": False,
                        "start_with_windows": False,
                        "poll_interval_minutes": 30,
                        "fx_rates": None,
                        "fx_rate_date": None,
                        "fx_fetched_at": None,
                        "widget_enabled": True,
                        "widget_position": None,
                    })

    def test_widget_preferences_are_validated_and_round_trip(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {"APPDATA": directory}):
            settings_file = Path(directory) / "HomeControlApp" / "settings.json"
            settings_file.parent.mkdir(parents=True)
            settings_file.write_text(
                '{"widget_enabled":"no","widget_position":{"x":"12","y":24}}',
                encoding="utf-8",
            )
            settings = load_settings()
            self.assertIs(settings["widget_enabled"], True)
            self.assertIsNone(settings["widget_position"])
            settings.update(widget_enabled=False, widget_position={"x": 120, "y": 240})
            save_settings(settings)
            restored = load_settings()
            self.assertIs(restored["widget_enabled"], False)
            self.assertEqual(restored["widget_position"], {"x": 120, "y": 240})

    def test_reconnect_preserves_checkpoint_state(self):
        settings = {"connected": False, "history_id": "123", "seen_ids": ["m1"]}
        with patch("homecontrol.settings.save_settings") as save:
            save_connection_state(settings)
        self.assertIs(settings["connected"], True)
        self.assertEqual(settings["history_id"], "123")
        self.assertEqual(settings["seen_ids"], ["m1"])
        save.assert_called_once_with(settings)


class PollingTests(unittest.TestCase):
    def test_baseline_and_new_high_dedup(self):
        service = Mock()
        service.users.return_value.getProfile.return_value.execute.return_value = {"historyId": "10"}
        state = {}
        self.assertEqual(poll_new_high(service, state), [])
        self.assertEqual(state["history_id"], "10")
        service.users.return_value.history.return_value.list.return_value.execute.return_value = {
            "history": [{"id": "11", "messagesAdded": [{"message": {"id": "m1", "labelIds": ["INBOX"]}}]}], "historyId": "11"}
        service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {"headers": [{"name": "Subject", "value": "Urgent: now"}]}}
        self.assertEqual(poll_new_high(service, state), ["m1"])
        self.assertEqual(poll_new_high(service, state), [])

    def test_history_expired_rebaselines(self):
        service = Mock(); state = {"history_id": "1", "seen_ids": []}
        err = RuntimeError("expired"); err.resp = Mock(status=404)
        service.users.return_value.history.return_value.list.return_value.execute.side_effect = err
        service.users.return_value.getProfile.return_value.execute.return_value = {"historyId": "25"}
        self.assertEqual(poll_new_high(service, state), [])
        self.assertEqual(state["history_id"], "25")

    def test_failure_does_not_advance_checkpoint(self):
        service = Mock(); state = {"history_id": "1", "seen_ids": []}
        service.users.return_value.history.return_value.list.return_value.execute.side_effect = RuntimeError("offline")
        with self.assertRaises(Exception): poll_new_high(service, state)
        self.assertEqual(state["history_id"], "1")

    def test_later_page_error_is_sanitized_and_does_not_advance(self):
        service = Mock(); state = {"history_id": "1", "seen_ids": []}
        listing = service.users.return_value.history.return_value.list
        listing.return_value.execute.side_effect = [
            {"history": [], "nextPageToken": "next"}, RuntimeError("secret API detail")]
        with self.assertRaises(GmailIntegrationError) as caught:
            poll_new_high(service, state)
        self.assertNotIn("secret API detail", str(caught.exception))
        self.assertEqual(state["history_id"], "1")
        self.assertEqual(listing.call_count, 2)

    def test_pagination_collects_messages_across_pages(self):
        service = Mock(); state = {"history_id": "1", "seen_ids": []}
        listing = service.users.return_value.history.return_value.list
        listing.return_value.execute.side_effect = [
            {"history": [{"id": "2", "messagesAdded": [{"message": {"id": "m1", "labelIds": ["INBOX"]}}]}], "nextPageToken": "next"},
            {"history": [{"id": "3", "messagesAdded": [{"message": {"id": "m2", "labelIds": ["INBOX"]}}]}], "historyId": "3"}]
        service.users.return_value.messages.return_value.get.side_effect = [
            Mock(execute=Mock(return_value={"payload": {"headers": [{"name": "Subject", "value": "Urgent: one"}]}})),
            Mock(execute=Mock(return_value={"payload": {"headers": [{"name": "Subject", "value": "Urgent: two"}]}}))]
        self.assertEqual(set(poll_new_high(service, state)), {"m1", "m2"})
        self.assertEqual(state["history_id"], "3")


class EntryPointTests(unittest.TestCase):
    def test_package_entry_point_launches_gui(self):
        from homecontrol.__main__ import main
        gui_module = types.ModuleType("homecontrol.gui")
        gui_module.main = Mock()
        with patch.dict("sys.modules", {"homecontrol.gui": gui_module}):
            main()
        gui_module.main.assert_called_once_with()


if __name__ == "__main__": unittest.main()

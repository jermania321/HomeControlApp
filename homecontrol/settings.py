"""Settings and durable Gmail polling state."""
import json
import os
import tempfile
from pathlib import Path

from .priority_classifier import DEFAULT_RULES


def settings_path():
    return Path(os.environ.get("APPDATA", Path.home())) / "HomeControlApp" / "settings.json"


def load_settings():
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("Settings must be a JSON object")
        connected = data.get("connected", False)
        if type(connected) is not bool:
            connected = False
        start_with_windows = data.get("start_with_windows", False)
        if type(start_with_windows) is not bool:
            start_with_windows = False
        widget_enabled = data.get("widget_enabled", True)
        if type(widget_enabled) is not bool:
            widget_enabled = True
        widget_position = data.get("widget_position")
        if (not isinstance(widget_position, dict)
                or type(widget_position.get("x")) is not int
                or type(widget_position.get("y")) is not int):
            widget_position = None
        else:
            widget_position = {"x": widget_position["x"], "y": widget_position["y"]}
        try:
            interval = max(1, min(1440, int(data.get("poll_interval_minutes", 30))))
        except (TypeError, ValueError):
            interval = 30
        return {"rules": data.get("rules", DEFAULT_RULES), "history_id": data.get("history_id"),
                "seen_ids": data.get("seen_ids", []), "connected": connected,
                "start_with_windows": start_with_windows, "poll_interval_minutes": interval,
                "fx_rates": data.get("fx_rates"), "fx_rate_date": data.get("fx_rate_date"),
                "fx_fetched_at": data.get("fx_fetched_at"),
                "widget_enabled": widget_enabled, "widget_position": widget_position}
    except (OSError, ValueError, TypeError):
        return {"rules": {k: list(v) for k, v in DEFAULT_RULES.items()}, "history_id": None, "seen_ids": [],
                "connected": False, "start_with_windows": False, "poll_interval_minutes": 30,
                "fx_rates": None, "fx_rate_date": None, "fx_fetched_at": None,
                "widget_enabled": True, "widget_position": None}


def save_settings(data):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def save_connection_state(settings):
    """Persist a successful connection without changing the polling checkpoint."""
    settings["connected"] = True
    save_settings(settings)


STARTUP_ENTRY_NAME = "HomeControlApp-start.bat"


def startup_entry_path(appdata=None):
    """Return this app's unique per-user Windows Startup entry path."""
    base = Path(appdata if appdata is not None else os.environ.get("APPDATA", Path.home()))
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / STARTUP_ENTRY_NAME


def set_start_with_windows(enabled, project_dir=None, appdata=None):
    """Create or remove only HomeControlApp's per-user startup launcher."""
    entry = startup_entry_path(appdata)
    if not enabled:
        try:
            entry.unlink()
        except FileNotFoundError:
            pass
        return
    project = Path(project_dir or Path(__file__).resolve().parent.parent).resolve()
    pythonw = project / ".venv" / "Scripts" / "pythonw.exe"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text('@echo off\r\n'
                     f'cd /d "{project}"\r\n'
                     f'start "" "{pythonw}" -m homecontrol\r\n', encoding="utf-8")

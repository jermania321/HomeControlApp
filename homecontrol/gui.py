"""PySide6 Gmail Priority Inbox desktop interface."""
import sys
import webbrowser
import ctypes
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QPoint, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QCheckBox,
    QTextEdit, QVBoxLayout, QWidget, QMenu, QStackedWidget, QSpinBox, QHeaderView, QFrame, QStyle, QBoxLayout,
    QScrollArea, QSizePolicy)

from .gmail_integration import (connect_gmail, fetch_latest_inbox, gmail_message_url,
                                poll_new_high)
from .settings import (load_settings, save_settings, save_connection_state,
                       set_start_with_windows)
from .priority_classifier import priority_color, priority_rank
from .dashboard_data import (CoalescingWorkQueue, fetch_fx, local_time,
                             validate_cached_rates)
from .desktop_widget import DesktopWidget


class Worker(QObject):
    done = Signal(object, object, object)
    def __init__(self, operation):
        super().__init__(); self.operation = operation
    def run(self):
        try: self.done.emit(self, self.operation(), None)
        except Exception as exc: self.done.emit(self, None, str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("HomeControl — Gmail Priority Inbox"); self.resize(1050, 720); self.setMinimumSize(760, 600)
        self.service = None; self.busy = False; self.settings = load_settings()
        self._high_mail_count = None
        self._pending = CoalescingWorkQueue()
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["Priority", "Sender", "Subject", "Date", "Snippet"])
        self.table.setFont(QFont("Segoe UI", 11))
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setMinimumHeight(240)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(48)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.cellClicked.connect(self.open_message)
        self.status = QLabel("Connect Gmail to begin.")
        connect = QPushButton("Connect Gmail"); connect.clicked.connect(self.connect)
        check = QPushButton("Check now"); check.clicked.connect(self.check_now)
        rules = QPushButton("Priority rules"); rules.clicked.connect(self.edit_rules)
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("start_with_windows", False))
        self.startup_checkbox.toggled.connect(self._startup_toggled)
        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.gmail_action_bar = bar
        [bar.addWidget(b) for b in (connect, check, rules, self.startup_checkbox)]
        self.pages = QStackedWidget()
        home = QWidget(); home_layout = QVBoxLayout(home)
        home_layout.setContentsMargins(20, 16, 20, 16)
        home_layout.setSpacing(12)
        dashboard = QWidget(); dashboard_layout = QVBoxLayout(dashboard)
        dashboard_layout.setContentsMargins(2, 4, 8, 12)
        dashboard_layout.setSpacing(16)
        self.fx_updated_label = QLabel("Rates loading…")
        self.fx_updated_label.setObjectName("mutedLabel")
        self.home_summary = QLabel("Connect Gmail to load your inbox summary.")
        self.home_summary.setWordWrap(True)
        self.poll_spin = QSpinBox(); self.poll_spin.setRange(1, 1440); self.poll_spin.setSuffix(" minutes")
        self.poll_spin.setValue(self.settings.get("poll_interval_minutes", 30)); self.poll_spin.valueChanged.connect(self.set_poll_interval)
        title = QLabel("Good day")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        subtitle = QLabel("Your time, exchange rates, and priority inbox at a glance.")
        subtitle.setObjectName("mutedLabel")
        dashboard_layout.addWidget(title)
        dashboard_layout.addWidget(subtitle)
        self.clock_row = QHBoxLayout()
        self.india_time_label = self._clock_card(self.clock_row, "India", "Asia/Kolkata")
        self.dallas_time_label = self._clock_card(self.clock_row, "Dallas", "America/Chicago")
        dashboard_layout.addLayout(self.clock_row)

        rates_heading = QLabel("Exchange rates")
        rates_heading.setObjectName("sectionHeading")
        self.rates_row = QHBoxLayout()
        self.usd_inr_label = self._metric_card(self.rates_row, "USD → INR")
        self.jpy_inr_label = self._metric_card(self.rates_row, "JPY → INR")
        dashboard_layout.addWidget(rates_heading)
        dashboard_layout.addLayout(self.rates_row)
        dashboard_layout.addWidget(self.fx_updated_label)

        gmail_card = QFrame()
        gmail_card.setObjectName("dashboardCard")
        gmail_layout = QVBoxLayout(gmail_card)
        gmail_heading = QLabel("Gmail Priority Inbox")
        gmail_heading.setObjectName("sectionHeading")
        gmail_layout.addWidget(gmail_heading)
        gmail_layout.addWidget(self.home_summary)
        gmail_controls = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.gmail_controls = gmail_controls
        gmail_controls.addWidget(QLabel("Check every"))
        gmail_controls.addWidget(self.poll_spin)
        gmail_controls.addStretch()
        gmail = QWidget(); layout = QVBoxLayout(gmail); layout.addLayout(bar); layout.addWidget(self.status); layout.addWidget(self.table)
        home_button = QPushButton("Home")
        gmail_button = QPushButton("Gmail Priority Inbox")
        home_button.setAccessibleName("Home")
        gmail_button.setAccessibleName("Gmail Priority Inbox")
        home_button.setCheckable(True); gmail_button.setCheckable(True)
        self._navigation_buttons = (home_button, gmail_button)
        home_button.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        gmail_button.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        gmail_layout.addLayout(gmail_controls)
        dashboard_layout.addWidget(gmail_card)
        dashboard_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(dashboard)
        home_layout.addWidget(scroll)
        self.pages.addWidget(home); self.pages.addWidget(gmail)
        shell = QWidget(); shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(12, 10, 12, 12)
        navigation = QHBoxLayout()
        navigation.addWidget(home_button); navigation.addWidget(gmail_button); navigation.addStretch()
        shell_layout.addLayout(navigation); shell_layout.addWidget(self.pages)
        self.setCentralWidget(shell)
        self.widget = DesktopWidget()
        self.widget.expandRequested.connect(self.show_and_activate)
        self.widget.hideRequested.connect(self.hide_widget)
        self.widget.positionChanged.connect(self._save_widget_position)
        self.widget_toggle = QPushButton("Show desktop widget")
        self.widget_toggle.clicked.connect(self.toggle_widget)
        navigation.addWidget(self.widget_toggle)
        if self.settings.get("widget_enabled", True):
            self._restore_widget()
        else:
            self._sync_widget_control()
        self.pages.currentChanged.connect(self._update_navigation)
        self._update_navigation(self.pages.currentIndex())
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("HomeControl is running — click to open; right-click for Exit")
        menu = QMenu()
        restore = QAction("Open HomeControl", self); restore.triggered.connect(self.show_and_activate)
        exit_action = QAction("Exit HomeControl", self); exit_action.triggered.connect(self.exit_app)
        menu.addAction(restore); menu.addSeparator(); menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self.timer = QTimer(self); self.timer.timeout.connect(self.check_now); self.timer.start(self.settings.get("poll_interval_minutes", 30) * 60 * 1000)
        self.clock_timer = QTimer(self); self.clock_timer.timeout.connect(self.update_clock); self.clock_timer.start(1000); self.update_clock()
        self.fx_timer = QTimer(self); self.fx_timer.timeout.connect(self.refresh_fx); self.fx_timer.start(6 * 60 * 60 * 1000)
        self._workers = []
        self._threads = []
        if self.settings.get("connected"):
            self.start_work(connect_gmail, self._reconnected, "connect")
        self.show_cached_fx()
        if not self.settings.get("fx_fetched_at") or self._fx_age_hours() >= 6: self.refresh_fx()

    @staticmethod
    def _clock_card(row, city, timezone_name):
        card = QFrame()
        card.setObjectName("dashboardCard")
        card.setMinimumWidth(0)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        heading = QLabel(f"{city} · {timezone_name}")
        heading.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        heading.setWordWrap(True)
        time_label = QLabel()
        time_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        layout.addWidget(heading)
        layout.addWidget(time_label)
        row.addWidget(card)
        return time_label

    @staticmethod
    def _metric_card(row, title):
        card = QFrame()
        card.setObjectName("dashboardCard")
        card.setMinimumWidth(0)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("mutedLabel")
        label.setWordWrap(True)
        value = QLabel("—")
        value.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))
        value.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(value)
        row.addWidget(card)
        return value

    def _update_navigation(self, active_index):
        destinations = ("Home", "Gmail Priority Inbox")
        for index, button in enumerate(self._navigation_buttons):
            active = index == active_index
            button.setChecked(active)
            current = destinations[active_index]
            destination = destinations[index]
            description = (f"Current destination: {current}."
                           if active else f"Navigate to {destination}.")
            button.setAccessibleDescription(description)

    def resizeEvent(self, event):
        if hasattr(self, "clock_row"):
            direction = (QBoxLayout.Direction.TopToBottom if self.width() < 900
                         else QBoxLayout.Direction.LeftToRight)
            self.clock_row.setDirection(direction)
            self.rates_row.setDirection(direction)
            self.gmail_action_bar.setDirection(
                QBoxLayout.Direction.TopToBottom if self.width() < 820
                else QBoxLayout.Direction.LeftToRight)
            self.gmail_controls.setDirection(
                QBoxLayout.Direction.TopToBottom if self.width() < 820
                else QBoxLayout.Direction.LeftToRight)
        super().resizeEvent(event)
        if hasattr(self, "table"):
            QTimer.singleShot(0, self._size_inbox_columns)

    def _size_inbox_columns(self):
        """Keep the inbox table fitted to the window while preserving readable fields."""
        available = self.table.viewport().width()
        for column, fraction, minimum in (
            (0, 0.05, 64),   # Priority
            (1, 0.22, 120),  # Sender
            (2, 0.14, 150),  # Subject
            (3, 0.25, 150),  # Date
        ):
            self.table.setColumnWidth(column, max(minimum, round(available * fraction)))

    def update_clock(self):
        self.india_time_label.setText(local_time("Asia/Kolkata"))
        dallas = local_time("America/Chicago")
        self.dallas_time_label.setText(dallas)
        self.widget.set_dallas_time(dallas)
    def _fx_age_hours(self):
        try: return (datetime.now(timezone.utc) - datetime.fromisoformat(self.settings["fx_fetched_at"])).total_seconds() / 3600
        except (KeyError, TypeError, ValueError): return float("inf")
    def show_cached_fx(self, error=None):
        rates = validate_cached_rates(self.settings.get("fx_rates"))
        if not rates:
            self.usd_inr_label.setText("Unavailable · INR per USD")
            self.jpy_inr_label.setText("Unavailable · INR per JPY")
            self.fx_updated_label.setText(error or "Rates could not be loaded.")
            self.widget.set_rates("Unavailable", "Unavailable", error or "Rates unavailable")
            return
        stale = self._fx_age_hours() >= 24
        self.usd_inr_label.setText(f"₹{rates['INR']:.2f} per USD")
        self.jpy_inr_label.setText(f"₹{rates['INR_per_JPY']:.4f} per JPY")
        status = f"Rates as of {self.settings.get('fx_rate_date') or 'unknown date'}"
        if stale: status += " · Stale"
        if error: status += f" · Refresh failed: {error}"
        self.fx_updated_label.setText(status)
        widget_status = f"As of {self.settings.get('fx_rate_date') or 'unknown date'}"
        if stale: widget_status += " · stale"
        if error: widget_status += " · refresh failed"
        self.widget.set_rates(f"₹{rates['INR']:.2f}", f"₹{rates['INR_per_JPY']:.4f}", widget_status)
    def refresh_fx(self):
        self.start_work(fetch_fx, self._fx_done, "fx")
    def _fx_done(self, result):
        rates, date = result; self.settings.update(fx_rates=rates, fx_rate_date=date, fx_fetched_at=datetime.now(timezone.utc).isoformat()); save_settings(self.settings); self.show_cached_fx()
    def set_poll_interval(self, minutes):
        self.settings['poll_interval_minutes'] = minutes; save_settings(self.settings); self.timer.start(minutes * 60 * 1000)
    def open_message(self, row, column):
        if column != 2: return
        message_id = self.table.item(row, 0).data(256) if self.table.item(row, 0) else ""
        url = gmail_message_url(message_id)
        if url: webbrowser.open(url)

    def start_work(self, operation, callback=None, category=None):
        if self.busy:
            self._pending.enqueue(category, operation, callback)
            return
        self.busy = True; thread = QThread(self); worker = Worker(operation); worker.moveToThread(thread)
        self._workers.append(worker); self._threads.append(thread)
        thread._worker = worker
        thread.started.connect(worker.run)
        worker.done.connect(self._finished)
        worker.done.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_finished)
        worker.done.connect(worker.deleteLater)
        self._callback = callback
        thread.start()
    def _thread_finished(self):
        thread = self.sender()
        worker = thread._worker
        if worker in self._workers: self._workers.remove(worker)
        if thread in self._threads: self._threads.remove(thread)
    def _finished(self, worker, result, error):
        self.busy = False
        callback = self._callback
        self._callback = None
        if error:
            if callback == self._fx_done:
                self.show_cached_fx(error)
            else:
                self.status.setText(error)
                if callback == getattr(self, "_gmail_done", None):
                    self.widget.set_high_mail_count(
                        self._high_mail_count,
                        stale=self._high_mail_count is not None,
                        unavailable=self._high_mail_count is None,
                    )
                elif callback == getattr(self, "_reconnected", None):
                    self.widget.set_high_mail_count(None, unavailable=True)
        elif callback: callback(result)
        if self._pending:
            category, operation, next_callback = self._pending.pop()
            self.start_work(operation, next_callback, category)
    def _reconnected(self, service):
        self.service = service
        save_connection_state(self.settings)
        self.check_now()
    def connect(self):
        self.status.setText("Opening Gmail authorization…")
        self.start_work(connect_gmail, self._reconnected, "connect")
    def check_now(self):
        if not self.service:
            self.status.setText("Connect Gmail first."); return
        self.status.setText("Checking Gmail…")
        self.widget.set_high_mail_count(self._high_mail_count,
                                        stale=self._high_mail_count is not None, loading=True)
        def poll():
            state = {"history_id": self.settings.get("history_id"), "seen_ids": self.settings.get("seen_ids", [])}
            alerts = poll_new_high(self.service, state, self.settings.get("rules"))
            rows = fetch_latest_inbox(self.service, rules=self.settings.get("rules"))
            return state, alerts, rows
        def done(result):
            state, alerts, rows = result; self.settings.update(state); save_settings(self.settings); self.render(rows)
            summary = f"{len(rows)} messages · {sum(r['priority']=='HIGH' for r in rows)} high · {sum(r['priority']=='MEDIUM' for r in rows)} medium"
            self._high_mail_count = sum(r["priority"] == "HIGH" for r in rows)
            self.widget.set_high_mail_count(self._high_mail_count)
            self.status.setText(summary); self.home_summary.setText(summary)
            if alerts: self.tray.showMessage("Gmail Priority Inbox", f"{len(alerts)} new high-priority message(s)")
        self._gmail_done = done
        self.start_work(poll, done, "gmail-poll")
    def render(self, rows):
        rows = sorted(rows, key=lambda row: priority_rank(row["priority"]))
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(("priority", "sender", "subject", "received_date", "snippet")):
                item = QTableWidgetItem(row[key])
                item.setBackground(QColor(priority_color(row["priority"])))
                item.setForeground(QColor("white"))
                self.table.setItem(i, j, item)
            self.table.item(i, 0).setData(256, row.get("id", ""))
            subject_item = self.table.item(i, 2); subject_item.setForeground(QColor("#9ecbff")); subject_item.setToolTip("Click to open this Gmail message")
    def _startup_toggled(self, enabled):
        try:
            set_start_with_windows(enabled)
            self.settings["start_with_windows"] = enabled
            save_settings(self.settings)
        except OSError as exc:
            self.startup_checkbox.blockSignals(True)
            self.startup_checkbox.setChecked(not enabled)
            self.startup_checkbox.blockSignals(False)
            QMessageBox.warning(self, "Startup setting", f"Could not update Windows startup: {exc}")
    def edit_rules(self):
        dialog = QDialog(self); dialog.setWindowTitle("Priority rules"); form = QFormLayout(dialog)
        high = QTextEdit(", ".join(self.settings["rules"].get("high", []))); medium = QTextEdit(", ".join(self.settings["rules"].get("medium", [])))
        high.setMaximumHeight(80); medium.setMaximumHeight(80); form.addRow("HIGH keywords (comma-separated)", high); form.addRow("MEDIUM keywords", medium)
        button = QPushButton("Save"); form.addRow(button)
        def save():
            self.settings["rules"] = {"high": [x.strip() for x in high.toPlainText().split(",") if x.strip()], "medium": [x.strip() for x in medium.toPlainText().split(",") if x.strip()]}; save_settings(self.settings); dialog.accept()
        button.clicked.connect(save); dialog.exec()
    def closeEvent(self, event): event.ignore(); self.hide(); self.tray.showMessage("Gmail Priority Inbox", "Still running in the system tray.")
    def _sync_widget_control(self):
        visible = self.widget.isVisible()
        self.widget_toggle.setText("Hide desktop widget" if visible else "Show desktop widget")
        self.widget_toggle.setAccessibleName(self.widget_toggle.text())
    def _restore_widget(self):
        position = self.settings.get("widget_position")
        point = None if position is None else QPoint(position["x"], position["y"])
        self.widget.restore_position(point)
        self.widget.show()
        self._sync_widget_control()
        self.show_cached_fx()
        if not self.service:
            self.widget.set_high_mail_count(None, unavailable=True)
        elif self._high_mail_count is not None:
            self.widget.set_high_mail_count(self._high_mail_count)
    def toggle_widget(self):
        if self.widget.isVisible():
            self.hide_widget()
        else:
            self.settings["widget_enabled"] = True
            save_settings(self.settings)
            self._restore_widget()
    def hide_widget(self):
        self.widget.hide()
        self.settings["widget_enabled"] = False
        save_settings(self.settings)
        self._sync_widget_control()
    def _save_widget_position(self, position):
        self.settings["widget_position"] = {"x": position.x(), "y": position.y()}
        save_settings(self.settings)
    def show_and_activate(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_and_activate()
    def exit_app(self):
        self.tray.hide()
        for thread in list(self._threads):
            thread.quit()
            thread.wait()
        QApplication.quit()


def main():
    if not acquire_single_instance():
        return
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))
    app.setStyleSheet("""
        QWidget { background-color: #171a21; color: #e7eaf0; }
        QMainWindow, QDialog { background-color: #171a21; }
        QScrollArea { background-color: transparent; }
        QFrame#dashboardCard {
            background-color: #222833; border: 1px solid #394354; border-radius: 10px;
        }
        QFrame#dashboardCard QLabel { background-color: transparent; border: none; }
        QFrame#desktopWidget {
            background-color: #202630; border: 1px solid #536176; border-radius: 12px;
        }
        QFrame#desktopWidgetHeader, QFrame#widgetRateCard { background-color: transparent; border: none; }
        QLabel#widgetTitle { color: #f2f5fa; font-weight: 700; font-size: 11pt; }
        QLabel#widgetTime { color: #ffffff; font-weight: 700; font-size: 21pt; }
        QLabel#widgetRateTitle, QLabel#widgetStatus { color: #a8b2c2; font-size: 8pt; }
        QLabel#widgetRateValue { color: #f4f6fa; font-weight: 600; font-size: 12pt; }
        QLabel#widgetHighMail { color: #ffcf70; font-weight: 700; font-size: 12pt; }
        QPushButton#widgetAction { padding: 4px 7px; font-size: 9pt; }
        QLabel#mutedLabel { color: #a8b2c2; }
        QLabel#sectionHeading { color: #f2f5fa; font-size: 15pt; font-weight: 600; }
        QPushButton {
            background-color: #292e38; color: #f4f6fa;
            border: 1px solid #414957; border-radius: 5px; padding: 7px 11px;
        }
        QPushButton:hover { background-color: #373f4d; }
        QPushButton:pressed { background-color: #202630; }
        QPushButton:checked { background-color: #304766; border-color: #6289b9; }
        QPushButton:focus { border: 2px solid #9ecbff; }
        QSpinBox, QTextEdit, QTableWidget {
            background-color: #20242c; color: #e7eaf0;
            border: 1px solid #414957; selection-background-color: #345b85;
        }
        QHeaderView::section {
            background-color: #292e38; color: #f4f6fa;
            font-weight: 600; padding: 7px; border: 1px solid #414957;
        }
        QTableCornerButton::section { background-color: #292e38; border: 1px solid #414957; }
        QCheckBox { spacing: 7px; }
        QMenu { background-color: #20242c; color: #e7eaf0; border: 1px solid #414957; }
        QMenu::item:selected { background-color: #345b85; }
    """)
    window = MainWindow(); window.show(); sys.exit(app.exec())


def acquire_single_instance():
    """Prevent duplicate app processes on Windows; retain the mutex for process lifetime."""
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_bool
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, "Local\\HomeControlApp.GmailPriorityInbox")
    if not handle:
        return False
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        activate_existing_window(kernel32)
        return False
    # Keep a module-level reference so the named mutex stays owned until exit.
    global _instance_mutex_handle
    _instance_mutex_handle = (kernel32, handle)
    return True


def activate_existing_window(kernel32):
    """Bring the already-running app back when the launcher is run again."""
    kernel32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
    kernel32.FindWindowW.restype = ctypes.c_void_p
    kernel32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
    kernel32.ShowWindow.restype = ctypes.c_bool
    kernel32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
    kernel32.SetForegroundWindow.restype = ctypes.c_bool
    import time
    for _ in range(20):
        window = kernel32.FindWindowW(None, "HomeControl — Gmail Priority Inbox")
        if window:
            kernel32.ShowWindow(window, 9)  # SW_RESTORE
            kernel32.SetForegroundWindow(window)
            return True
        time.sleep(0.1)
    return False

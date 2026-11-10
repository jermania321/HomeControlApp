"""PySide6 Gmail Priority Inbox desktop interface."""
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSystemTrayIcon, QTableWidget, QTableWidgetItem, QCheckBox,
    QTextEdit, QVBoxLayout, QWidget, QMenu)

from gmail_integration import connect_gmail, fetch_latest_inbox, poll_new_high
from homecontrol import load_settings, save_settings, save_connection_state, set_start_with_windows
from priority_classifier import priority_color, priority_rank


class Worker(QObject):
    done = Signal(object, object, object)
    def __init__(self, operation):
        super().__init__(); self.operation = operation
    def run(self):
        try: self.done.emit(self, self.operation(), None)
        except Exception as exc: self.done.emit(self, None, str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("HomeControl — Gmail Priority Inbox"); self.resize(950, 580)
        self.service = None; self.busy = False; self.settings = load_settings()
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(["Priority", "Sender", "Subject", "Date", "Snippet"])
        self.status = QLabel("Connect Gmail to begin.")
        connect = QPushButton("Connect Gmail"); connect.clicked.connect(self.connect)
        check = QPushButton("Check now"); check.clicked.connect(self.check_now)
        rules = QPushButton("Priority rules"); rules.clicked.connect(self.edit_rules)
        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setChecked(self.settings.get("start_with_windows", False))
        self.startup_checkbox.toggled.connect(self._startup_toggled)
        bar = QHBoxLayout(); [bar.addWidget(b) for b in (connect, check, rules, self.startup_checkbox)]
        layout = QVBoxLayout(); layout.addLayout(bar); layout.addWidget(self.status); layout.addWidget(self.table)
        root = QWidget(); root.setLayout(layout); self.setCentralWidget(root)
        self.tray = QSystemTrayIcon(self); self.tray.setToolTip("Gmail Priority Inbox")
        menu = QMenu(); restore = QAction("Open", self); restore.triggered.connect(self.show); exit_action = QAction("Exit", self); exit_action.triggered.connect(self.exit_app)
        menu.addAction(restore); menu.addAction(exit_action); self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason: self.show() if reason == QSystemTrayIcon.ActivationReason.Trigger else None); self.tray.show()
        self.timer = QTimer(self); self.timer.timeout.connect(self.check_now); self.timer.start(60 * 60 * 1000)
        self._workers = []
        self._threads = []
        if self.settings.get("connected"):
            self.start_work(connect_gmail, self._reconnected)

    def start_work(self, operation, callback=None):
        if self.busy: return
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
        if error: self.status.setText(error); return
        if callback: callback(result)
    def _reconnected(self, service):
        self.service = service
        save_connection_state(self.settings)
        self.check_now()
    def connect(self):
        self.status.setText("Opening Gmail authorization…")
        self.start_work(connect_gmail, self._reconnected)
    def check_now(self):
        if not self.service:
            self.status.setText("Connect Gmail first."); return
        self.status.setText("Checking Gmail…")
        def poll():
            state = {"history_id": self.settings.get("history_id"), "seen_ids": self.settings.get("seen_ids", [])}
            alerts = poll_new_high(self.service, state, self.settings.get("rules"))
            rows = fetch_latest_inbox(self.service, rules=self.settings.get("rules"))
            return state, alerts, rows
        def done(result):
            state, alerts, rows = result; self.settings.update(state); save_settings(self.settings); self.render(rows)
            self.status.setText(f"{len(rows)} messages · {sum(r['priority']=='HIGH' for r in rows)} high · {sum(r['priority']=='MEDIUM' for r in rows)} medium")
            if alerts: self.tray.showMessage("Gmail Priority Inbox", f"{len(alerts)} new high-priority message(s)")
        self.start_work(poll, done)
    def render(self, rows):
        rows = sorted(rows, key=lambda row: priority_rank(row["priority"]))
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(("priority", "sender", "subject", "received_date", "snippet")):
                item = QTableWidgetItem(row[key])
                item.setBackground(QColor(priority_color(row["priority"])))
                item.setForeground(QColor("white"))
                self.table.setItem(i, j, item)
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
    def exit_app(self):
        self.tray.hide()
        for thread in list(self._threads):
            thread.quit()
            thread.wait()
        QApplication.quit()


def main():
    app = QApplication(sys.argv); window = MainWindow(); window.show(); sys.exit(app.exec())

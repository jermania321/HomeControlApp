"""Always-on-top compact desktop view for the HomeControl dashboard."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class _DragHandle(QFrame):
    """Header surface that lets the frameless widget be repositioned."""

    positionChanged = Signal(QPoint)

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self.positionChanged.emit(self._window.pos())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DesktopWidget(QFrame):
    """Compact always-on-top view that remains independent of the main window."""

    expandRequested = Signal()
    hideRequested = Signal()
    positionChanged = Signal(QPoint)

    def __init__(self):
        flags = (Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                 | Qt.WindowType.WindowStaysOnTopHint)
        super().__init__(None, flags)
        self.setObjectName("desktopWidget")
        self.setWindowTitle("HomeControl desktop widget")
        self.setAccessibleName("HomeControl desktop widget")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = _DragHandle(self)
        header.setObjectName("desktopWidgetHeader")
        header.positionChanged.connect(self.positionChanged)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("HomeControl")
        title.setObjectName("widgetTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        expand = QPushButton("Full")
        expand.setObjectName("widgetAction")
        expand.setAccessibleName("Open full HomeControl dashboard")
        expand.setToolTip("Open the full dashboard")
        expand.clicked.connect(self.expandRequested)
        header_layout.addWidget(expand)

        hide = QPushButton("Hide")
        hide.setObjectName("widgetAction")
        hide.setAccessibleName("Hide desktop widget")
        hide.setToolTip("Hide this widget; HomeControl will keep running")
        hide.clicked.connect(self.hideRequested)
        header_layout.addWidget(hide)
        layout.addWidget(header)

        self.dallas_time_label = QLabel("Dallas  —:—")
        self.dallas_time_label.setObjectName("widgetTime")
        layout.addWidget(self.dallas_time_label)

        rates = QHBoxLayout()
        rates.setSpacing(8)
        self.usd_rate_label = self._rate_card("USD → INR")
        self.jpy_rate_label = self._rate_card("JPY → INR")
        rates.addWidget(self.usd_rate_label[0])
        rates.addWidget(self.jpy_rate_label[0])
        layout.addLayout(rates)

        self.rate_status_label = QLabel("Rates loading…")
        self.rate_status_label.setObjectName("widgetStatus")
        layout.addWidget(self.rate_status_label)

        self.high_mail_label = QLabel("HIGH mail: —")
        self.high_mail_label.setObjectName("widgetHighMail")
        layout.addWidget(self.high_mail_label)

        self.gmail_status_label = QLabel("Connect Gmail to see priority count")
        self.gmail_status_label.setObjectName("widgetStatus")
        self.gmail_status_label.setWordWrap(True)
        layout.addWidget(self.gmail_status_label)

        self.setMinimumHeight(self.sizeHint().height())

    @staticmethod
    def _rate_card(title):
        card = QFrame()
        card.setObjectName("widgetRateCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(9, 7, 9, 7)
        card_layout.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("widgetRateTitle")
        value = QLabel("—")
        value.setObjectName("widgetRateValue")
        card_layout.addWidget(heading)
        card_layout.addWidget(value)
        return card, value

    def set_dallas_time(self, value):
        self.dallas_time_label.setText(f"Dallas  {value}")

    def set_rates(self, usd_value, jpy_value, status):
        self.usd_rate_label[1].setText(usd_value)
        self.jpy_rate_label[1].setText(jpy_value)
        self.rate_status_label.setText(status)

    def set_high_mail_count(self, count, *, stale=False, unavailable=False, loading=False):
        if unavailable:
            self.high_mail_label.setText("HIGH mail: unavailable")
        elif count is None:
            self.high_mail_label.setText("HIGH mail: —")
        else:
            suffix = " · stale" if stale else ""
            self.high_mail_label.setText(f"HIGH mail: {count}{suffix}")
        if loading:
            self.gmail_status_label.setText("Checking Gmail…")
        elif unavailable:
            self.gmail_status_label.setText("Connect Gmail or check your connection")
        elif stale:
            self.gmail_status_label.setText("Last successful inbox check; refresh pending")
        elif count is not None:
            self.gmail_status_label.setText("Current count from the latest inbox check")
        else:
            self.gmail_status_label.setText("Connect Gmail to see priority count")

    def restore_position(self, saved_position=None):
        """Restore a saved position, clamped to a currently available screen."""
        self.adjustSize()
        screens = QGuiApplication.screens()
        if not screens:
            return

        screen = QGuiApplication.screenAt(saved_position) if saved_position is not None else None
        if screen is None:
            screen = QGuiApplication.primaryScreen() or screens[0]
        area = screen.availableGeometry()
        if saved_position is None:
            position = QPoint(area.right() - self.width() - 18,
                              area.bottom() - self.height() - 18)
        else:
            position = saved_position

        max_x = max(area.left(), area.right() - self.width() + 1)
        max_y = max(area.top(), area.bottom() - self.height() + 1)
        self.move(max(area.left(), min(position.x(), max_x)),
                  max(area.top(), min(position.y(), max_y)))

    def closeEvent(self, event):
        self.hideRequested.emit()
        event.accept()

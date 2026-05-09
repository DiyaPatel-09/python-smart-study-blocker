"""
gui.py - PyQt5 main window for Smart Study Distraction Blocker
"""

import logging
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QSpinBox, QTabWidget, QFrame, QMessageBox, QSplitter,
    QTextEdit, QStatusBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor

from database import Database
from blocker import AppBlocker
from scheduler import SessionScheduler
from analytics import AnalyticsWidget

try:
    from plyer import notification as plyer_notify
    PLYER_AVAILABLE = True
except Exception:
    PLYER_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Catppuccin Mocha dark palette ─────────────────────────────────────────────
STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #45475a;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #313244;
    color: #cdd6f4;
    padding: 7px 18px;
    border-radius: 4px 4px 0 0;
}
QTabBar::tab:selected {
    background: #45475a;
    color: #cba6f7;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 16px;
}
QPushButton:hover { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton#startBtn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#startBtn:hover { background-color: #94e2d5; }
QPushButton#stopBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#stopBtn:hover { background-color: #eba0ac; }
QPushButton#pauseBtn {
    background-color: #fab387;
    color: #1e1e2e;
    font-weight: bold;
}
QLineEdit, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 8px;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid #cba6f7; }
QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
}
QListWidget::item:selected { background-color: #45475a; color: #cba6f7; }
QListWidget::item:hover { background-color: #313244; }
QTextEdit {
    background-color: #181825;
    color: #a6e3a1;
    border: 1px solid #45475a;
    border-radius: 5px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}
QStatusBar { background-color: #181825; color: #6c7086; }
QFrame#card {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
}
QLabel#timerLabel {
    color: #cba6f7;
    font-size: 42px;
    font-weight: bold;
}
QLabel#statusLabel {
    font-size: 14px;
    font-weight: bold;
    padding: 4px 12px;
    border-radius: 10px;
}
"""


class SignalBridge(QObject):
    """Thread-safe signal bridge for callbacks from background threads."""
    process_killed = pyqtSignal(str)
    session_complete = pyqtSignal()
    tick = pyqtSignal(int)
    paused = pyqtSignal()
    resumed = pyqtSignal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.blocker = AppBlocker()
        self.scheduler = SessionScheduler(interval_seconds=3)
        self.signals = SignalBridge()
        self._session_duration = 0

        self._wire_signals()
        self._build_ui()
        self._load_blocked_apps()
        self.setWindowTitle("Smart Study Distraction Blocker")
        self.resize(900, 680)
        self.setStyleSheet(STYLE)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _wire_signals(self):
        self.scheduler.on_tick = lambda s: self.signals.tick.emit(s)
        self.scheduler.on_complete = lambda: self.signals.session_complete.emit()
        self.scheduler.on_paused = lambda: self.signals.paused.emit()
        self.scheduler.on_resumed = lambda: self.signals.resumed.emit()
        self.blocker.set_on_blocked_callback(
            lambda name: self.signals.process_killed.emit(name)
        )

        self.signals.tick.connect(self._on_tick)
        self.signals.session_complete.connect(self._on_session_complete)
        self.signals.process_killed.connect(self._on_process_killed)
        self.signals.paused.connect(self._on_paused)
        self.signals.resumed.connect(self._on_resumed)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        tabs = QTabWidget()
        tabs.addTab(self._build_session_tab(), "Session")
        tabs.addTab(self._build_apps_tab(), "Blocked Apps")
        tabs.addTab(self._build_analytics_tab(), "Analytics")
        tabs.addTab(self._build_log_tab(), "Activity Log")
        root.addWidget(tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _build_session_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Timer display card
        timer_card = QFrame()
        timer_card.setObjectName("card")
        tc_layout = QVBoxLayout(timer_card)
        tc_layout.setAlignment(Qt.AlignCenter)

        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignCenter)
        tc_layout.addWidget(self.timer_label)

        self.status_label = QLabel("● Stopped")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #f38ba8; background: #2a1a1a; border-radius: 10px; padding: 4px 12px;")
        tc_layout.addWidget(self.status_label)

        layout.addWidget(timer_card)

        # Duration input
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (minutes):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 480)
        self.duration_spin.setValue(25)
        self.duration_spin.setFixedWidth(90)
        dur_row.addWidget(self.duration_spin)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        # Control buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  Start Session")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self._start_session)

        self.pause_btn = QPushButton("⏸  Pause")
        self.pause_btn.setObjectName("pauseBtn")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)

        self.stop_btn = QPushButton("■  Stop Session")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self._stop_session)
        self.stop_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        # Session history
        layout.addWidget(QLabel("Session History:"))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(160)
        layout.addWidget(self.history_list)
        self._refresh_history()

        layout.addStretch()
        return w

    def _build_apps_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Add app process name (e.g. chrome.exe, discord.exe):"))

        add_row = QHBoxLayout()
        self.app_input = QLineEdit()
        self.app_input.setPlaceholderText("Enter process name...")
        self.app_input.returnPressed.connect(self._add_app)
        add_row.addWidget(self.app_input)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_app)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self.apps_list = QListWidget()
        layout.addWidget(self.apps_list)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_app)
        layout.addWidget(remove_btn)

        # Quick-add common apps
        layout.addWidget(QLabel("Quick add:"))
        quick_row = QHBoxLayout()
        for name in ["chrome.exe", "brave.exe", "discord.exe", "spotify.exe", "steam.exe"]:
            btn = QPushButton(name)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, n=name: self._quick_add(n))
            quick_row.addWidget(btn)
        layout.addLayout(quick_row)

        return w

    def _build_analytics_tab(self) -> QWidget:
        self.analytics_widget = AnalyticsWidget(self.db)
        return self.analytics_widget

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Activity Log:"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.log_view.clear)
        layout.addWidget(clear_btn)
        return w

    # ── Session control ───────────────────────────────────────────────────────

    def _start_session(self):
        apps = self.db.get_blocked_apps()
        if not apps:
            QMessageBox.warning(self, "No Apps Blocked",
                                "Add at least one app to the blocked list before starting.")
            return

        duration = self.duration_spin.value()
        self._session_duration = duration
        self.blocker.set_blocked_apps(apps)

        # Kill already-running blocked apps immediately, then start continuous monitor
        killed = self.blocker.kill_blocked_processes()
        for k in killed:
            self._log(f"Killed on start: {k}")

        self.blocker.start_blocking()   # continuous real-time monitoring thread
        self.scheduler.start(duration)

        self._set_status_running()
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.duration_spin.setEnabled(False)

        self._notify("Study Session Started",
                     f"Blocking {len(apps)} app(s) for {duration} minutes. Focus up!")
        self._log(f"Session started: {duration} min, blocking {apps}")
        self.status_bar.showMessage(f"Session running — {duration} minutes")

    def _stop_session(self):
        elapsed = self.scheduler.elapsed_seconds
        self.scheduler.stop()
        self.blocker.stop_blocking()    # stop continuous monitor
        completed_min = elapsed // 60
        if completed_min > 0:
            self.db.log_session(completed_min, completed=False)
        self._end_session_ui(completed=False)
        self._log(f"Session stopped manually after {elapsed}s")

    def _toggle_pause(self):
        if self.scheduler.is_paused:
            # Resume: restart blocking immediately
            self.blocker.start_blocking()
            self.scheduler.resume()
        else:
            # Pause: stop blocking so apps can be used during the break
            self.blocker.stop_blocking()
            self.scheduler.pause()

    # ── Scheduler callbacks (on main thread via signals) ──────────────────────

    def _on_tick(self, elapsed: int):
        remaining = self.scheduler.remaining_seconds
        self.timer_label.setText(SessionScheduler.format_time(remaining))

    def _on_session_complete(self):
        self.blocker.stop_blocking()    # stop continuous monitor
        self.db.log_session(self._session_duration, completed=True)
        self._end_session_ui(completed=True)
        self._notify("Study Session Completed",
                     f"Great work! You studied for {self._session_duration} minutes.")
        self._log(f"Session completed: {self._session_duration} min")
        self.analytics_widget.refresh()
        self._refresh_history()

    def _on_process_killed(self, name: str):
        self._log(f"Blocked & killed: {name}")
        self.status_bar.showMessage(f"Blocked: {name}")

    def _on_paused(self):
        self.status_label.setText("⏸ Paused — Apps Unblocked")
        self.status_label.setStyleSheet(
            "color: #fab387; background: #2a1e10; border-radius: 10px; padding: 4px 12px;")
        self.pause_btn.setText("▶  Resume")
        self._log("Session paused — blocked apps are temporarily allowed")

    def _on_resumed(self):
        self._set_status_running()
        self.pause_btn.setText("⏸  Pause")
        self._log("Session resumed — blocking active again")

    # ── App list management ───────────────────────────────────────────────────

    def _load_blocked_apps(self):
        self.apps_list.clear()
        for app in self.db.get_blocked_apps():
            self.apps_list.addItem(app)

    def _add_app(self):
        name = self.app_input.text().strip()
        if not name:
            return
        if self.db.add_blocked_app(name):
            self.apps_list.addItem(name.lower())
            self._log(f"Added to block list: {name}")
        else:
            QMessageBox.information(self, "Already Exists", f"'{name}' is already in the list.")
        self.app_input.clear()

    def _remove_app(self):
        item = self.apps_list.currentItem()
        if not item:
            return
        name = item.text()
        self.db.remove_blocked_app(name)
        self.apps_list.takeItem(self.apps_list.row(item))
        self._log(f"Removed from block list: {name}")

    def _quick_add(self, name: str):
        if self.db.add_blocked_app(name):
            self.apps_list.addItem(name)
            self._log(f"Quick-added: {name}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _end_session_ui(self, completed: bool):
        self.timer_label.setText("00:00")
        self.status_label.setText("● Stopped")
        self.status_label.setStyleSheet(
            "color: #f38ba8; background: #2a1a1a; border-radius: 10px; padding: 4px 12px;")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸  Pause")
        self.stop_btn.setEnabled(False)
        self.duration_spin.setEnabled(True)
        self.status_bar.showMessage("Session ended" if completed else "Session stopped")

    def _set_status_running(self):
        self.status_label.setText("● Running")
        self.status_label.setStyleSheet(
            "color: #a6e3a1; background: #1a2a1a; border-radius: 10px; padding: 4px 12px;")

    def _refresh_history(self):
        self.history_list.clear()
        for s in self.db.get_sessions()[:20]:
            status = "✓" if s["completed"] else "✗"
            self.history_list.addItem(
                f"{status}  {s['date']}  —  {s['duration_minutes']} min"
            )

    def _log(self, msg: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")

    def _notify(self, title: str, message: str):
        if PLYER_AVAILABLE:
            try:
                plyer_notify.notify(
                    title=title,
                    message=message,
                    app_name="Study Blocker",
                    timeout=5
                )
            except Exception as e:
                logger.warning(f"Notification failed: {e}")

    def closeEvent(self, event):
        if self.scheduler.is_running:
            reply = QMessageBox.question(
                self, "Session Active",
                "A study session is running. Stop it and exit?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.scheduler.stop()
        self.db.close()
        event.accept()

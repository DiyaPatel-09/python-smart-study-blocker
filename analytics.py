"""
analytics.py - Matplotlib charts embedded in PyQt5 for the analytics dashboard
"""

import matplotlib
matplotlib.use("Qt5Agg")

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget
from PyQt5.QtCore import Qt


DARK_BG = "#1e1e2e"
ACCENT = "#cba6f7"
BAR_COLOR = "#89b4fa"
BAR_COLOR2 = "#a6e3a1"
TEXT_COLOR = "#cdd6f4"


class AnalyticsWidget(QWidget):
    """Embeddable analytics dashboard showing daily and weekly study charts."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Analytics Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color: {ACCENT}; font-size: 16px; font-weight: bold; padding: 6px;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid #45475a; background: {DARK_BG}; }}
            QTabBar::tab {{ background: #313244; color: {TEXT_COLOR}; padding: 6px 14px; }}
            QTabBar::tab:selected {{ background: #45475a; color: {ACCENT}; }}
        """)

        self.daily_canvas = self._make_canvas()
        self.weekly_canvas = self._make_canvas()

        tabs.addTab(self.daily_canvas, "Daily (last 30 days)")
        tabs.addTab(self.weekly_canvas, "Weekly (last 8 weeks)")
        layout.addWidget(tabs)

        total = self.db.get_total_study_time()
        hours, mins = divmod(total, 60)
        summary = QLabel(f"Total study time: {hours}h {mins}m")
        summary.setAlignment(Qt.AlignCenter)
        summary.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px; padding: 4px;")
        layout.addWidget(summary)

        self.refresh()

    def _make_canvas(self) -> FigureCanvas:
        fig = Figure(facecolor=DARK_BG)
        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(280)
        return canvas

    def refresh(self):
        """Redraw both charts with latest data."""
        self._draw_daily()
        self._draw_weekly()

    def _draw_daily(self):
        rows = self.db.get_daily_totals()
        rows = list(reversed(rows))  # oldest → newest
        dates = [r[0] for r in rows]
        minutes = [r[1] for r in rows]

        fig = self.daily_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111, facecolor=DARK_BG)
        if dates:
            bars = ax.bar(range(len(dates)), minutes, color=BAR_COLOR, width=0.6)
            ax.set_xticks(range(len(dates)))
            ax.set_xticklabels(
                [d[5:] for d in dates],  # show MM-DD
                rotation=45, ha="right", fontsize=8, color=TEXT_COLOR
            )
            # Value labels on bars
            for bar, val in zip(bars, minutes):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"{val}m", ha="center", va="bottom",
                    fontsize=7, color=TEXT_COLOR
                )
        else:
            ax.text(0.5, 0.5, "No data yet", transform=ax.transAxes,
                    ha="center", va="center", color=TEXT_COLOR, fontsize=12)

        ax.set_title("Daily Study Time (minutes)", color=ACCENT, fontsize=11)
        ax.set_ylabel("Minutes", color=TEXT_COLOR, fontsize=9)
        ax.tick_params(colors=TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor("#45475a")
        fig.tight_layout()
        self.daily_canvas.draw()

    def _draw_weekly(self):
        rows = self.db.get_weekly_totals()
        rows = list(reversed(rows))
        weeks = [r[0] for r in rows]
        minutes = [r[1] for r in rows]

        fig = self.weekly_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111, facecolor=DARK_BG)
        if weeks:
            bars = ax.bar(range(len(weeks)), minutes, color=BAR_COLOR2, width=0.6)
            ax.set_xticks(range(len(weeks)))
            ax.set_xticklabels(weeks, rotation=30, ha="right", fontsize=8, color=TEXT_COLOR)
            for bar, val in zip(bars, minutes):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"{val}m", ha="center", va="bottom",
                    fontsize=7, color=TEXT_COLOR
                )
        else:
            ax.text(0.5, 0.5, "No data yet", transform=ax.transAxes,
                    ha="center", va="center", color=TEXT_COLOR, fontsize=12)

        ax.set_title("Weekly Study Time (minutes)", color=ACCENT, fontsize=11)
        ax.set_ylabel("Minutes", color=TEXT_COLOR, fontsize=9)
        ax.tick_params(colors=TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor("#45475a")
        fig.tight_layout()
        self.weekly_canvas.draw()

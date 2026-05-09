"""
scheduler.py - Session timing and periodic blocking checks
"""

import threading
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class SessionScheduler:
    """
    Manages a study session timer and runs a blocking check every `interval` seconds.
    All callbacks are invoked on a background thread.
    """

    def __init__(self, interval_seconds: int = 3):
        self.interval = interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # _resume_event: SET = running, CLEARED = paused
        # The loop blocks on wait() when the event is cleared (paused).
        self._resume_event = threading.Event()
        self._resume_event.set()  # start in running state

        # Callbacks
        self.on_tick: Callable[[int], None] | None = None        # (elapsed_seconds)
        self.on_check: Callable[[], None] | None = None          # periodic block check
        self.on_complete: Callable[[], None] | None = None       # session finished
        self.on_paused: Callable[[], None] | None = None
        self.on_resumed: Callable[[], None] | None = None

        self.duration_seconds: int = 0
        self.elapsed_seconds: int = 0
        self.is_running: bool = False
        self.is_paused: bool = False

    def start(self, duration_minutes: int):
        """Start a new session for `duration_minutes` minutes."""
        if self.is_running:
            return
        self.duration_seconds = duration_minutes * 60
        self.elapsed_seconds = 0
        self._stop_event.clear()
        self._resume_event.set()  # ensure running state on (re)start
        self.is_running = True
        self.is_paused = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Session started: {duration_minutes} minutes")

    def stop(self):
        """Forcefully stop the session."""
        self._stop_event.set()
        self._resume_event.set()  # unblock loop if currently paused so thread can exit
        self.is_running = False
        self.is_paused = False
        logger.info("Session stopped manually.")

    def pause(self):
        """Pause the session timer."""
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self._resume_event.clear()  # clearing blocks the loop
            if self.on_paused:
                self.on_paused()
            logger.info("Session paused.")

    def resume(self):
        """Resume a paused session."""
        if self.is_running and self.is_paused:
            self.is_paused = False
            self._resume_event.set()    # setting unblocks the loop
            if self.on_resumed:
                self.on_resumed()
            logger.info("Session resumed.")

    def _run(self):
        """Main loop running on background thread."""
        while not self._stop_event.is_set():
            # Block here while paused; wakes instantly on resume() or stop()
            self._resume_event.wait()

            if self._stop_event.is_set():
                break

            time.sleep(1)
            self.elapsed_seconds += 1

            if self.on_tick:
                self.on_tick(self.elapsed_seconds)

            # Session complete
            if self.elapsed_seconds >= self.duration_seconds:
                self.is_running = False
                if self.on_complete:
                    self.on_complete()
                break

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.duration_seconds - self.elapsed_seconds)

    @staticmethod
    def format_time(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

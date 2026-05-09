"""
blocker.py - Real-time process monitoring and killing using psutil.

A dedicated background thread continuously scans running processes every
1-2 seconds. If a blocked app is detected it is immediately terminated.
A global `blocking` flag controls whether monitoring is active.
"""

import psutil
import logging
import platform
import subprocess
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class AppBlocker:
    def __init__(self, interval: float = 1.5):
        """
        :param interval: Seconds between each process scan (default 1.5s).
        """
        self.interval = interval
        self.blocked_apps: list[str] = []          # lowercase process names
        self.blocking: bool = False                 # global on/off flag
        self.on_blocked: Callable[[str], None] | None = None  # fired on each kill

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_blocked_apps(self, apps: list[str]):
        """
        Update the blocked apps list.
        Strips '.exe' so 'discord.exe' becomes the keyword 'discord',
        which then matches discord.exe, discordptb.exe, discord helper.exe, etc.
        """
        keywords = []
        for a in apps:
            a = a.lower().strip()
            if a.endswith(".exe"):
                a = a[:-4]   # 'discord.exe' → 'discord'
            if a:
                keywords.append(a)
        self.blocked_apps = keywords

    def set_on_blocked_callback(self, callback: Callable[[str], None]):
        self.on_blocked = callback

    def start_blocking(self):
        """Start the continuous monitoring thread."""
        if self.blocking:
            return  # already running
        # Wait for any previous thread to finish before starting fresh
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=3)
        self.blocking = True
        self._stop_event.clear()  # must clear AFTER old thread exits
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="AppBlockerThread")
        self._thread.start()
        logger.info(f"Blocking started. Watching: {self.blocked_apps}")

    def stop_blocking(self):
        """Stop the monitoring thread."""
        self.blocking = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("Blocking stopped.")

    def kill_blocked_processes(self) -> list[str]:
        """
        Single-pass scan: kill every running process whose name contains
        any blocked keyword (substring match, case-insensitive).

        Example: keyword 'discord' matches discord.exe, discordptb.exe,
        discord helper (32 bit).exe, etc.

        Returns list of killed process names.
        """
        killed = []
        keywords = list(self.blocked_apps)  # snapshot for thread safety
        if not keywords:
            return killed

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                raw_name = proc.info.get("name")
                if not raw_name:          # skip processes with no name
                    continue
                proc_name_lower = raw_name.lower()

                # Substring match: kill if ANY keyword is found in the process name
                for keyword in keywords:
                    if keyword in proc_name_lower:
                        try:
                            proc.kill()
                            killed.append(raw_name)
                            logger.info(
                                f"Killed '{raw_name}' (PID {proc.info['pid']}) "
                                f"— matched keyword '{keyword}'"
                            )
                            if self.on_blocked:
                                self.on_blocked(raw_name)
                        except psutil.NoSuchProcess:
                            pass   # already gone by the time we tried
                        except psutil.AccessDenied:
                            logger.warning(
                                f"Access denied killing '{raw_name}' "
                                f"(PID {proc.info['pid']}) — try running as administrator"
                            )
                        break  # no need to check other keywords for this process

            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                pass
            except psutil.ZombieProcess:
                pass
            except Exception as e:
                logger.error(f"Unexpected error scanning processes: {e}")

        return killed

    # ── Internal loop ─────────────────────────────────────────────────────────

    def _monitor_loop(self):
        """
        Runs on a background thread. Continuously scans processes while
        `self.blocking` is True, sleeping `self.interval` seconds between scans.
        Uses a fresh Event per session so stale state from a previous session
        never causes the loop to exit prematurely.
        """
        logger.info("Monitor loop started.")
        while self.blocking:
            self.kill_blocked_processes()
            # wait() with timeout acts as interruptible sleep.
            # Because _stop_event is freshly cleared in start_blocking(),
            # this only returns early when stop_blocking() sets it.
            interrupted = self._stop_event.wait(timeout=self.interval)
            if interrupted:
                break  # stop_blocking() was called
        logger.info("Monitor loop exited.")

    # ── Website blocking via hosts file (optional, needs admin) ───────────────

    HOSTS_PATH = (
        r"C:\Windows\System32\drivers\etc\hosts"
        if platform.system() == "Windows"
        else "/etc/hosts"
    )
    MARKER_START = "# --- STUDY BLOCKER START ---"
    MARKER_END   = "# --- STUDY BLOCKER END ---"
    REDIRECT     = "127.0.0.1"

    def block_websites(self, domains: list[str]):
        """Append domain redirects to the hosts file (requires admin/root)."""
        try:
            with open(self.HOSTS_PATH, "r") as f:
                content = f.read()
            if self.MARKER_START in content:
                return
            entries = "\n".join(f"{self.REDIRECT} {d}" for d in domains)
            block = f"\n{self.MARKER_START}\n{entries}\n{self.MARKER_END}\n"
            with open(self.HOSTS_PATH, "a") as f:
                f.write(block)
            self._flush_dns()
            logger.info(f"Blocked websites: {domains}")
        except PermissionError:
            logger.warning("Cannot modify hosts file — run as administrator for website blocking.")
        except Exception as e:
            logger.error(f"Website blocking error: {e}")

    def unblock_websites(self):
        """Remove study-blocker entries from the hosts file."""
        try:
            with open(self.HOSTS_PATH, "r") as f:
                lines = f.readlines()
            inside = False
            cleaned = []
            for line in lines:
                if self.MARKER_START in line:
                    inside = True
                    continue
                if self.MARKER_END in line:
                    inside = False
                    continue
                if not inside:
                    cleaned.append(line)
            with open(self.HOSTS_PATH, "w") as f:
                f.writelines(cleaned)
            self._flush_dns()
            logger.info("Unblocked websites.")
        except PermissionError:
            logger.warning("Cannot modify hosts file — run as administrator.")
        except Exception as e:
            logger.error(f"Website unblocking error: {e}")

    def _flush_dns(self):
        try:
            if platform.system() == "Windows":
                subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
            elif platform.system() == "Darwin":
                subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
            else:
                subprocess.run(["systemd-resolve", "--flush-caches"], capture_output=True)
        except Exception:
            pass

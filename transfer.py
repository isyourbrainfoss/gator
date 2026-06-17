"""transfer.py – Thread-safe subprocess wrappers for croc send/receive.

All public callbacks (on_log, on_code, on_finished, …) are dispatched to the
GLib main loop via ``GLib.idle_add`` so callers can safely update GTK widgets.

Usage from the Application class::

    transfer = CrocSendTransfer(
        settings=self.settings,
        files=["/path/to/file"],
        excluded=[],
        text="",
        on_log=lambda msg: self.append_log(self.send_log, msg),
        on_code=self.show_code_and_qr,
        on_finished=self.transfer_finished_send,
    )
    transfer.start()       # non-blocking – spawns a daemon thread
    transfer.cancel()      # safe to call from any thread
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from typing import Any

from gi.repository import GLib

from settings import (
    CODE_IS_PREFIX,
    CROC_BINARY,
    DEFAULT_MULTICAST,
    DEFAULT_PORT,
    DEFAULT_TRANSFERS,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_global_args(settings: dict[str, Any]) -> list[str]:
    """Build croc global flags from a settings dict.

    These flags are valid before the ``send`` / implicit-receive subcommand and
    apply to both operations.  Having a single source of truth prevents the
    receive path from silently ignoring settings that the send path respects.
    """
    args: list[str] = []
    curve = settings.get("curve", "p256")
    if curve != "p256":
        args += ["--curve", curve]
    relay = settings.get("relay", "").strip()
    if relay:
        args += ["--relay", relay]
    relay6 = settings.get("relay6", "").strip()
    if relay6:
        args += ["--relay6", relay6]
    relay_pass = settings.get("pass", "").strip()
    if relay_pass:
        args += ["--pass", relay_pass]
    if settings.get("internal_dns", False):
        args += ["--internal-dns"]
    if settings.get("debug", False):
        args += ["--debug"]
    if settings.get("yes", False):
        args += ["--yes"]
    if settings.get("no_compress", False):
        args += ["--no-compress"]
    if settings.get("ask", False):
        args += ["--ask"]
    if settings.get("local", False):
        args += ["--local"]
    if settings.get("overwrite", False):
        args += ["--overwrite"]
    if settings.get("testing", False):
        args += ["--testing"]
    if settings.get("quiet", False):
        args += ["--quiet"]
    if settings.get("disable_clipboard", False):
        args += ["--disable-clipboard"]
    if settings.get("extended_clipboard", False):
        args += ["--extended-clipboard"]
    multicast = settings.get("multicast", DEFAULT_MULTICAST).strip()
    if multicast != DEFAULT_MULTICAST:
        args += ["--multicast", multicast]
    ip = settings.get("ip", "").strip()
    if ip:
        args += ["--ip", ip]
    socks5 = settings.get("socks5", "").strip()
    if socks5:
        args += ["--socks5", socks5]
    connect = settings.get("connect", "").strip()
    if connect:
        args += ["--connect", connect]
    throttle_upload = settings.get("throttle_upload", "").strip()
    if throttle_upload:
        args += ["--throttleUpload", throttle_upload]
    return args


# ── Base class ───────────────────────────────────────────────────────────────


class CrocTransfer:
    """Base class that owns a croc subprocess and provides thread-safe
    cancellation, stdout draining, and main-loop callback dispatch."""

    def __init__(
        self,
        on_log: Callable[[str], None],
        on_finished: Callable[[], None],
    ) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self.canceled = False

        # Callbacks – always dispatched on the GLib main loop.
        self._on_log = on_log
        self._on_finished = on_finished

    # ── public API ───────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn the background thread.  Subclasses must implement ``_run``."""
        self.canceled = False
        Thread(target=self._run, daemon=True).start()

    def cancel(self) -> None:
        """Kill the subprocess from any thread.  ``wait()`` happens in the
        background thread after stdout drains."""
        with self._lock:
            proc = self._proc
        if proc is not None:
            self.canceled = True
            proc.kill()

    # ── internal helpers ─────────────────────────────────────────────────

    def _log(self, text: str) -> None:
        """Dispatch a log line to the main loop."""
        GLib.idle_add(self._on_log, text)

    def _finish(self) -> None:
        """Dispatch the finished callback to the main loop."""
        GLib.idle_add(self._on_finished)

    def _set_proc(self, proc: subprocess.Popen[str]) -> None:
        with self._lock:
            self._proc = proc

    def _clear_proc(self) -> None:
        with self._lock:
            self._proc = None

    def _drain_stdout(self, proc: subprocess.Popen[str]) -> list[str]:
        """Read all lines from *proc.stdout*, dispatch log callbacks, and
        return the raw lines.  Always closes the pipe."""
        lines: list[str] = []
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                lines.append(line)
                self._log(line)
        finally:
            proc.stdout.close()
        return lines

    def _run(self) -> None:
        raise NotImplementedError


# ── Send ─────────────────────────────────────────────────────────────────────


class CrocSendTransfer(CrocTransfer):
    """Wraps ``croc send`` in a background thread.

    Parameters
    ----------
    settings : dict
        The application settings dict (read-only during the transfer).
    files : list[str]
        Absolute paths of files/folders to send.
    excluded : list[str]
        Paths to exclude from the transfer.
    text : str
        Text to send via ``--text`` (empty string means no text).
    on_log : callback(str)
        Called on the main loop for every stdout line.
    on_code : callback(str)
        Called on the main loop when the transfer code is parsed.
    on_finished : callback()
        Called on the main loop when the subprocess exits.
    """

    def __init__(
        self,
        settings: dict[str, Any],
        files: list[str],
        excluded: list[str],
        text: str,
        on_log: Callable[[str], None],
        on_code: Callable[[str], None],
        on_finished: Callable[[], None],
    ) -> None:
        super().__init__(on_log=on_log, on_finished=on_finished)
        self._settings = settings
        self._files = list(files)
        self._excluded = list(excluded)
        self._text = text
        self._on_code = on_code

    def _build_args(self) -> list[str]:
        """Assemble the full ``croc send …`` command line."""
        s = self._settings
        args = [CROC_BINARY] + build_global_args(s) + ["send"]

        custom = s.get("default_code", "").strip()
        if custom:
            args += ["--code", custom]
        hash_alg = s.get("hash", "xxhash")
        if hash_alg != "xxhash":
            args += ["--hash", hash_alg]
        if s.get("zip_folder", False):
            args += ["--zip"]
        if self._text:
            args += ["--text", self._text]
        if s.get("no_local", False):
            args += ["--no-local"]
        if s.get("no_multi", False):
            args += ["--no-multi"]
        if s.get("git", False):
            args += ["--git"]
        port = s.get("port", DEFAULT_PORT)
        if port != DEFAULT_PORT:
            args += ["--port", str(port)]
        transfers = s.get("transfers", DEFAULT_TRANSFERS)
        if transfers != DEFAULT_TRANSFERS:
            args += ["--transfers", str(transfers)]
        if s.get("qr", False):
            args += ["--qr"]
        if self._excluded:
            excludes = ",".join(Path(p).name for p in self._excluded)
            args += ["--exclude", excludes]
        if self._files:
            args += self._files
        return args

    def _run(self) -> None:
        args = self._build_args()

        # Log the command for debugging
        display = [f'"{a}"' if " " in a else a for a in args]
        self._log(f"Running: {' '.join(display)}")
        self._log("Starting croc send")

        try:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            logger.exception("Failed to start croc send")
            self._log(f"Error starting croc: {e}")
            self._finish()
            return

        self._set_proc(proc)
        try:
            for raw in proc.stdout:
                line = raw.rstrip()
                self._log(line)
                if line.startswith(CODE_IS_PREFIX):
                    code = line[len(CODE_IS_PREFIX) :].strip()
                    GLib.idle_add(self._on_code, code)
        finally:
            proc.stdout.close()

        proc.wait()
        self._clear_proc()
        self._finish()


# ── Receive ──────────────────────────────────────────────────────────────────


class CrocReceiveTransfer(CrocTransfer):
    """Wraps ``croc`` (implicit receive via ``CROC_SECRET``) in a background thread.

    Parameters
    ----------
    settings : dict
        The application settings dict (read-only during the transfer).
    code : str
        The transfer code entered by the user.
    save_dir : str
        Directory in which to receive files.
    on_log : callback(str)
        Called on the main loop for every stdout line.
    on_text_received : callback(str)
        Called on the main loop when inline text content is captured.
    on_transfer_complete : callback()
        Called on the main loop when a *file* transfer succeeds (not text).
    on_finished : callback()
        Called on the main loop when the subprocess exits (always).
    """

    def __init__(
        self,
        settings: dict[str, Any],
        code: str,
        save_dir: str,
        on_log: Callable[[str], None],
        on_text_received: Callable[[str], None],
        on_transfer_complete: Callable[[], None],
        on_finished: Callable[[], None],
    ) -> None:
        super().__init__(on_log=on_log, on_finished=on_finished)
        self._settings = settings
        self._code = code
        self._save_dir = save_dir
        self._on_text_received = on_text_received
        self._on_transfer_complete = on_transfer_complete

    def _run(self) -> None:
        env = os.environ.copy()
        env["CROC_SECRET"] = self._code
        args = [CROC_BINARY] + build_global_args(self._settings)

        # Snapshot dir contents before transfer to robustly distinguish
        # file receives from text receives (independent of croc stdout format).
        before: set[str] = set()
        try:
            before = set(os.listdir(self._save_dir))
        except OSError:
            pass

        try:
            proc = subprocess.Popen(
                args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self._save_dir,
            )
        except Exception as e:
            logger.exception("Failed to start croc receive")
            self._log(f"Error starting croc: {e}")
            self._finish()
            return

        self._set_proc(proc)

        # Collect non-progress output lines. For --text sends these will be
        # the payload. We avoid depending on exact phrasing like "Receiving (<-"
        # which can vary across croc versions; we decide text vs files via
        # files actually landing in the directory + exit code.
        text_lines: list[str] = []
        saw_file_indicator = False
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                self._log(line)
                if "Receiving file (" in line:
                    saw_file_indicator = True
                if self._is_likely_content_line(line):
                    text_lines.append(line)
        finally:
            proc.stdout.close()

        proc.wait()
        returncode = proc.returncode
        self._clear_proc()

        # ── Determine what was transferred using directory changes (robust) ──
        received_files = False
        try:
            after = set(os.listdir(self._save_dir))
            new_items = after - before
            non_text_new = [n for n in new_items if not n.startswith("croc-stdin-")]
            if non_text_new:
                received_files = True
        except OSError:
            # If we cannot list, fall back to indicators seen
            received_files = saw_file_indicator

        # ── Post-transfer actions ────────────────────────────────────────
        text_delivered = False
        # Inline text captured from stdout (croc send --text)
        if text_lines:
            text = "\n".join(text_lines).strip()
            if text:
                GLib.idle_add(self._on_text_received, text)
                text_delivered = True

        # Temp file written by croc for text (fallback path)
        if not text_delivered and returncode == 0 and not self.canceled:
            if self._check_temp_text_file():
                text_delivered = True

        # Successful file transfer (not text)
        if (
            returncode == 0
            and not self.canceled
            and received_files
            and not text_delivered
        ):
            GLib.idle_add(self._on_transfer_complete)

        self._finish()

    def _is_likely_content_line(self, line: str) -> bool:
        """Return True for lines that are probable text-payload content.

        Filters out progress bars, status messages, and blank lines so that
        collected lines for a --text transfer are the actual payload.
        """
        s = line.strip()
        if not s:
            return False
        if "%" in s or "|" in s:
            return False
        low = s.lower()
        # Typical non-content status lines from croc
        if s.startswith("Receiving file ("):
            return False
        if "transfer finished" in low:
            return False
        if "code is invalid" in low:
            return False
        if s.startswith("Code is:"):
            return False
        if "error" in low and len(s) < 80:
            # short error-ish lines are status
            return False
        if s.startswith("Waiting") or s.startswith("Sending"):
            return False
        return True

    def _check_temp_text_file(self) -> bool:
        """Look for a ``croc-stdin-*`` temp file and surface its content.

        Returns True if a text payload was found and delivered.
        """
        temp_file = None
        try:
            for filename in os.listdir(self._save_dir):
                if filename.startswith("croc-stdin-"):
                    temp_file = os.path.join(self._save_dir, filename)
                    break
        except OSError as e:
            logger.warning("Could not list save directory: %s", e)
            return False
        if temp_file:
            try:
                with open(temp_file) as f:
                    text = f.read()
                os.remove(temp_file)
                text = text.strip()
                if text:
                    GLib.idle_add(self._on_text_received, text)
                    return True
            except OSError as e:
                logger.warning("Could not read temp text file: %s", e)
                self._log(f"Error reading received text: {e}")
        return False

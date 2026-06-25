"""transfer.py – Gio.Subprocess wrappers for croc send/receive.

All callbacks run on the GLib main loop via async I/O (no worker threads).
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from .settings import CODE_IS_PREFIX, CROC_BINARY

logger = logging.getLogger(__name__)

_PROGRESS_RE = re.compile(r"(\d{1,3})%")
_CODE_IS_RE = re.compile(r"^code is:\s*", re.IGNORECASE)


def normalize_croc_code(code: str) -> str:
    """Normalize a user-entered croc code (paste quirks, spacing)."""
    normalized = code.strip()
    normalized = _CODE_IS_RE.sub("", normalized)
    return normalized.replace(" ", "-")


def detect_transfer_phase(line: str) -> str | None:
    """Return ``hashing``, ``sending``, ``receiving``, or None from a croc line."""
    low = line.lower()
    if "hashing" in low and "%" in line:
        return "hashing"
    if parse_progress_fraction(line) is not None:
        if "receiving" in low:
            return "receiving"
        return "sending"
    return None


def build_receive_args(settings: dict[str, Any], code: str) -> list[str]:
    """Build argv for a croc receive invocation."""
    return [CROC_BINARY] + build_global_args(settings) + [normalize_croc_code(code)]


def parse_progress_fraction(line: str) -> float | None:
    """Return 0.0–1.0 if *line* looks like a croc progress update."""
    match = _PROGRESS_RE.search(line)
    if not match:
        return None
    value = int(match.group(1))
    if 0 <= value <= 100:
        return value / 100.0
    return None


def split_croc_output(
    chunk: str, buffer: str = ""
) -> tuple[str, list[tuple[str, bool]]]:
    """Split croc stdout on ``\\n`` and ``\\r``.

    Croc redraws transfer progress with carriage returns when stdout is not a TTY.
    Returns ``(remaining_buffer, [(segment, from_newline), ...])``.
    """
    buf = buffer + chunk
    segments: list[tuple[str, bool]] = []
    while True:
        idx_n = buf.find("\n")
        idx_r = buf.find("\r")
        if idx_n == -1 and idx_r == -1:
            break
        if idx_n == -1:
            idx, from_newline = idx_r, False
        elif idx_r == -1:
            idx, from_newline = idx_n, True
        else:
            idx, from_newline = (idx_r, False) if idx_r < idx_n else (idx_n, True)
        segment = buf[:idx]
        buf = buf[idx + 1 :]
        if segment:
            segments.append((segment, from_newline))
    return buf, segments


def build_global_args(settings: dict[str, Any]) -> list[str]:
    """Build croc global flags from a settings dict."""
    args: list[str] = []
    curve = (settings.get("curve") or "").strip()
    if curve:
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
    multicast = (settings.get("multicast") or "").strip()
    if multicast:
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


class CrocTransfer:
    """Base class for croc subprocess transfers using Gio.Subprocess."""

    def __init__(
        self,
        on_log: Callable[[str], None],
        on_finished: Callable[[], None],
        on_progress: Callable[[float], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._proc: Gio.Subprocess | None = None
        self._stream: Gio.DataInputStream | None = None
        self.canceled = False
        self._finished = False
        self._waiting_exit = False
        self._lines: list[str] = []
        self._read_buf = ""
        self._on_log = on_log
        self._on_finished = on_finished
        self._on_progress = on_progress
        self._on_status = on_status

    def start(self) -> None:
        """Launch croc asynchronously on the GLib main loop."""
        self.canceled = False
        self._finished = False
        self._waiting_exit = False
        self._lines = []
        self._read_buf = ""
        try:
            self._launch()
        except GLib.Error as e:
            logger.exception("Failed to start croc")
            self._on_log(f"Error starting croc: {e.message}")
            self._on_finished()

    def cancel(self) -> None:
        """Terminate the running subprocess."""
        if self.canceled or self._finished:
            return
        self.canceled = True
        proc = self._proc
        if proc is None:
            self._cleanup()
            return
        try:
            proc.force_exit()
        except GLib.Error as e:
            logger.warning("Failed to cancel croc: %s", e.message)
        self._wait_for_exit()

    def _launch(self) -> None:
        raise NotImplementedError

    def _spawn(
        self,
        argv: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        flags = Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE
        launcher = Gio.SubprocessLauncher.new(flags)
        if env is not None:
            for key, value in env.items():
                launcher.setenv(key, value, True)
        if cwd is not None:
            launcher.set_cwd(cwd)
        self._proc = launcher.spawnv(argv)
        pipe = self._proc.get_stdout_pipe()
        if pipe is None:
            self._wait_for_exit()
            return
        self._stream = Gio.DataInputStream.new(pipe)
        self._read_chunk()

    def _read_chunk(self) -> None:
        if self._stream is None:
            self._wait_for_exit()
            return
        self._stream.read_bytes_async(
            4096,
            GLib.PRIORITY_DEFAULT,
            None,
            self._on_read_chunk,
            None,
        )

    def _on_read_chunk(
        self,
        _stream: Gio.DataInputStream,
        result: Gio.AsyncResult,
        *_user_data: Any,
    ) -> None:
        if self._finished:
            return
        if self._stream is None:
            self._wait_for_exit()
            return
        try:
            data = self._stream.read_bytes_finish(result)
        except GLib.Error:
            self._wait_for_exit()
            return
        if data.get_size() == 0:
            self._flush_read_buffer()
            self._wait_for_exit()
            return
        chunk = bytes(data.get_data()).decode("utf-8", errors="replace")
        self._consume_output(chunk)
        self._read_chunk()

    def _consume_output(self, chunk: str) -> None:
        self._read_buf, segments = split_croc_output(chunk, self._read_buf)
        for segment, from_newline in segments:
            self._emit_segment(segment, from_newline=from_newline)
        trailing = self._read_buf.rstrip()
        if trailing:
            self._handle_line(trailing)

    def _flush_read_buffer(self) -> None:
        trailing = self._read_buf.rstrip()
        if trailing:
            self._emit_segment(trailing, from_newline=True)
        self._read_buf = ""

    def _emit_segment(self, segment: str, *, from_newline: bool) -> None:
        stripped = segment.rstrip()
        if not stripped:
            return
        is_progress = parse_progress_fraction(stripped) is not None
        if from_newline or not is_progress:
            self._lines.append(stripped)
            self._on_log(stripped)
        self._handle_line(stripped)

    def _handle_line(self, line: str) -> None:
        if self._on_status is not None:
            phase = detect_transfer_phase(line)
            if phase is not None:
                self._on_status(phase)
        if self._on_progress is not None:
            fraction = parse_progress_fraction(line)
            if fraction is not None:
                self._on_progress(fraction)

    def _wait_for_exit(self) -> None:
        if self._finished:
            return
        if self._proc is None:
            self._cleanup()
            return
        if self._waiting_exit:
            return
        self._waiting_exit = True
        self._proc.wait_async(None, self._on_wait_complete)

    def _on_wait_complete(self, proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            proc.wait_finish(result)
        except GLib.Error as e:
            logger.warning("croc wait failed: %s", e.message)
        self._cleanup()

    def _cleanup(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._proc = None
        self._stream = None
        self._on_finished()


class CrocSendTransfer(CrocTransfer):
    """Wraps ``croc send`` using Gio.Subprocess."""

    def __init__(
        self,
        settings: dict[str, Any],
        files: list[str],
        excluded: list[str],
        text: str,
        on_log: Callable[[str], None],
        on_code: Callable[[str], None],
        on_finished: Callable[[], None],
        on_progress: Callable[[float], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            on_log=on_log,
            on_finished=on_finished,
            on_progress=on_progress,
            on_status=on_status,
        )
        self._settings = settings
        self._files = list(files)
        self._excluded = list(excluded)
        self._text = text
        self._on_code = on_code

    def _build_args(self) -> list[str]:
        s = self._settings
        args = [CROC_BINARY] + build_global_args(s) + ["send"]
        custom = s.get("default_code", "").strip()
        if custom:
            args += ["--code", custom]
        hash_alg = (s.get("hash") or "").strip()
        if hash_alg:
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
        port = int(s.get("port") or 0)
        if port > 0:
            args += ["--port", str(port)]
        transfers = int(s.get("transfers") or 0)
        if transfers > 0:
            args += ["--transfers", str(transfers)]
        if s.get("qr", False):
            args += ["--qr"]
        if self._excluded:
            excludes = ",".join(Path(p).name for p in self._excluded)
            args += ["--exclude", excludes]
        if self._files:
            args += self._files
        return args

    def _handle_line(self, line: str) -> None:
        super()._handle_line(line)
        if line.startswith(CODE_IS_PREFIX):
            code = line[len(CODE_IS_PREFIX) :].strip()
            self._on_code(code)

    def _launch(self) -> None:
        args = self._build_args()
        display = [f'"{a}"' if " " in a else a for a in args]
        self._on_log(f"Running: {' '.join(display)}")
        self._on_log("Starting croc send")
        self._spawn(args)


class CrocReceiveTransfer(CrocTransfer):
    """Wraps croc receive (via CROC_SECRET) using Gio.Subprocess."""

    def __init__(
        self,
        settings: dict[str, Any],
        code: str,
        save_dir: str,
        on_log: Callable[[str], None],
        on_text_received: Callable[[str], None],
        on_transfer_complete: Callable[[], None],
        on_finished: Callable[[], None],
        on_progress: Callable[[float], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            on_log=on_log,
            on_finished=on_finished,
            on_progress=on_progress,
            on_status=on_status,
        )
        self._settings = settings
        self._code = code
        self._save_dir = save_dir
        self._on_text_received = on_text_received
        self._on_transfer_complete = on_transfer_complete
        self._returncode = -1
        self._before: set[str] = set()
        self._saw_file_indicator = False

    def _is_likely_content_line(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if "%" in s or "|" in s:
            return False
        low = s.lower()
        if s.startswith("Receiving file ("):
            return False
        if "transfer finished" in low:
            return False
        if "code is invalid" in low:
            return False
        if s.startswith("Code is:"):
            return False
        if "error" in low and len(s) < 80:
            return False
        if s.startswith("Waiting") or s.startswith("Sending"):
            return False
        return True

    def _handle_line(self, line: str) -> None:
        super()._handle_line(line)
        if "Receiving file (" in line:
            self._saw_file_indicator = True

    def _launch(self) -> None:
        try:
            self._before = set(os.listdir(self._save_dir))
        except OSError:
            self._before = set()
        code = normalize_croc_code(self._code)
        self._code = code
        args = build_receive_args(self._settings, code)
        display = [f'"{a}"' if " " in a else a for a in args]
        self._on_log(f"Running: {' '.join(display)}")
        self._on_log(f'Receiving with code "{code}"')
        self._spawn(args, cwd=self._save_dir)

    def _on_wait_complete(self, proc: Gio.Subprocess, result: Gio.AsyncResult) -> None:
        try:
            self._returncode = proc.wait_finish(result)
        except GLib.Error as e:
            logger.warning("croc wait failed: %s", e.message)
            self._returncode = -1
        self._post_process()
        self._cleanup()

    def _post_process(self) -> None:
        text_lines = [ln for ln in self._lines if self._is_likely_content_line(ln)]
        received_files = False
        try:
            after = set(os.listdir(self._save_dir))
            new_items = after - self._before
            non_text_new = [n for n in new_items if not n.startswith("croc-stdin-")]
            if non_text_new:
                received_files = True
        except OSError:
            received_files = self._saw_file_indicator

        text_delivered = False
        if text_lines:
            text = "\n".join(text_lines).strip()
            if text:
                self._on_text_received(text)
                text_delivered = True

        if not text_delivered and self._returncode == 0 and not self.canceled:
            if self._check_temp_text_file():
                text_delivered = True

        if (
            self._returncode == 0
            and not self.canceled
            and received_files
            and not text_delivered
        ):
            self._on_transfer_complete()

    def _check_temp_text_file(self) -> bool:
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
                    self._on_text_received(text)
                    return True
            except OSError as e:
                logger.warning("Could not read temp text file: %s", e)
                self._on_log(f"Error reading received text: {e}")
        return False

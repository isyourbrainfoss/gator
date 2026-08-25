"""transfer.py – Gio.Subprocess wrappers for croc send/receive.

All callbacks run on the GLib main loop via async I/O (no worker threads).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from .settings import CROC_BINARY

logger = logging.getLogger(__name__)

_PROGRESS_RE = re.compile(r"(\d{1,3})%")
_CODE_IS_RE = re.compile(r"^code is:\s*", re.IGNORECASE)
_ACCEPT_PROMPT_RE = re.compile(r"^Accept .+ \(.*\)\? \(Y/n\)", re.IGNORECASE)
_CROC_STATUS_PREFIXES = (
    "connecting",
    "securing channel",
    "receiving (<-",
    "receiving (->",
    "sending (<-",
    "sending (->",
    "running:",
    "waiting",
    "receiving file (",
    "receiving transfer",
    "starting croc",
    "code is:",
    "hashing",
)
_CROC_STATUS_SUBSTRINGS = (
    "transfer finished",
    "code is invalid",
    "on unix systems",
    "croc_secret",
    "classic mode",
    "enter receive code",
    "(y/n)",
    "room (secure channel)",
    "peer disconnected",
    "peer error",
    "refusing files",
    "could not connect",
    "permission denied",
)
_REDACT_FLAGS = {"--pass", "--code", "--text"}
_MAX_LOG_LINES = 500
_PROGRESS_UI_MS = 100

# User-facing error kinds (translated at the UI layer).
ERROR_INVALID_CODE = "invalid_code"
ERROR_PEER = "peer"
ERROR_REFUSED = "refused"
ERROR_RELAY = "relay"
ERROR_PERMISSION = "permission"
ERROR_SPAWN = "spawn"
ERROR_FAILED = "failed"

_ERROR_KIND_MATCHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        ERROR_INVALID_CODE,
        ("code is invalid", "could not find room", "room does not exist"),
    ),
    (ERROR_PEER, ("peer disconnected", "peer error")),
    (ERROR_REFUSED, ("refusing files", "refusing file")),
    (
        ERROR_RELAY,
        (
            "could not connect",
            "connection refused",
            "i/o timeout",
            "no such host",
            "network is unreachable",
            "dial tcp",
            "timeout",
        ),
    ),
    (
        ERROR_PERMISSION,
        ("permission denied", "read-only file system", "operation not permitted"),
    ),
)


def is_croc_status_line(line: str) -> bool:
    """True if *line* is croc CLI status output, not received text payload."""
    s = line.strip()
    if not s:
        return True
    if "%" in s or "|" in s:
        return True
    low = s.lower()
    if low.startswith(_CROC_STATUS_PREFIXES):
        return True
    if _ACCEPT_PROMPT_RE.match(s):
        return True
    if any(sub in low for sub in _CROC_STATUS_SUBSTRINGS):
        return True
    if low.startswith("sending ") and "code is:" not in low:
        return True
    return False


def normalize_croc_code(code: str) -> str:
    """Normalize a user-entered croc code (paste quirks, spacing)."""
    normalized = code.strip()
    normalized = _CODE_IS_RE.sub("", normalized)
    return normalized.replace(" ", "-")


def extract_send_code(line: str) -> str | None:
    """Return the transfer code from a croc 'Code is:' line, or None."""
    stripped = line.strip()
    match = _CODE_IS_RE.match(stripped)
    if match is None:
        return None
    code = stripped[match.end() :].strip()
    return code or None


def classify_croc_error(line: str) -> str | None:
    """Return an error kind for a croc status line, or None."""
    low = line.lower()
    for kind, needles in _ERROR_KIND_MATCHERS:
        if any(needle in low for needle in needles):
            return kind
    return None


def redact_argv(argv: list[str]) -> list[str]:
    """Copy argv with values of secret flags replaced by ``***``."""
    out: list[str] = []
    hide_next = False
    for arg in argv:
        if hide_next:
            out.append("***")
            hide_next = False
            continue
        if arg in _REDACT_FLAGS:
            out.append(arg)
            hide_next = True
            continue
        out.append(arg)
    return out


def format_argv_for_log(argv: list[str]) -> str:
    """Shell-ish display of argv with secrets redacted."""
    display = [f'"{a}"' if " " in a else a for a in redact_argv(argv)]
    return " ".join(display)


def apply_subprocess_status(proc: Gio.Subprocess) -> tuple[int, bool]:
    """Return ``(exit_status, successful)`` after ``wait_finish``.

    ``Gio.Subprocess.wait_finish`` is a boolean (wait completed), not a Unix
    status. Callers must use ``get_exit_status`` / ``get_successful``.
    """
    try:
        if proc.get_if_exited():
            return int(proc.get_exit_status()), bool(proc.get_successful())
        if proc.get_if_signaled():
            return 128, False
    except (AttributeError, GLib.Error) as e:
        logger.warning("Could not read croc exit status: %s", e)
    return -1, False


def detect_transfer_phase(line: str) -> str | None:
    """Return hashing/sending/receiving/waiting/connecting, or None."""
    low = line.lower()
    if "hashing" in low and "%" in line:
        return "hashing"
    if parse_progress_fraction(line) is not None:
        if "receiving" in low:
            return "receiving"
        return "sending"
    if low.startswith("waiting") or "waiting for" in low:
        return "waiting"
    if low.startswith("connecting") or low.startswith("securing"):
        return "connecting"
    return None


def build_receive_args(
    settings: dict[str, Any],
    *,
    force_yes: bool = False,
    disable_clipboard: bool = False,
) -> list[str]:
    """Build argv for a croc receive invocation (code goes in ``CROC_SECRET``)."""
    return [CROC_BINARY] + build_global_args(
        settings,
        force_yes=force_yes,
        disable_clipboard=disable_clipboard,
        ignore_stdin=True,
    )


def receive_env_for_code(code: str) -> dict[str, str]:
    """Env vars croc v10+ expects for non-TTY receive (no positional code)."""
    return {"CROC_SECRET": normalize_croc_code(code)}


def parse_progress_fraction(line: str) -> float | None:
    """Return 0.0–1.0 if *line* looks like a croc progress update."""
    if "%" not in line:
        return None
    low = line.lower()
    if (
        "|" not in line
        and "hashing" not in low
        and "receiving" not in low
        and "sending" not in low
    ):
        return None
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


def build_global_args(
    settings: dict[str, Any],
    *,
    force_yes: bool = False,
    disable_clipboard: bool = False,
    ignore_stdin: bool = False,
) -> list[str]:
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
    if force_yes or settings.get("yes", False):
        args += ["--yes"]
    if settings.get("no_compress", False):
        args += ["--no-compress"]
    if settings.get("ask", False):
        args += ["--ask"]
    if settings.get("local", False):
        args += ["--local"]
    if settings.get("overwrite", False):
        args += ["--overwrite"]
    elif settings.get("rename", False):
        args += ["--rename"]
    if settings.get("testing", False):
        args += ["--testing"]
    if settings.get("quiet", False):
        args += ["--quiet"]
    if disable_clipboard or settings.get("disable_clipboard", False):
        args += ["--disable-clipboard"]
    if ignore_stdin:
        args += ["--ignore-stdin"]
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
        self._cancellable: Gio.Cancellable | None = None
        self.canceled = False
        self.success = False
        self.exit_status = -1
        self.error_kind: str | None = None
        self._finished = False
        self._waiting_exit = False
        self._lines: list[str] = []
        self._read_buf = ""
        self._on_log = on_log
        self._on_finished = on_finished
        self._on_progress = on_progress
        self._on_status = on_status
        self._pending_progress: float | None = None
        self._pending_phase: str | None = None
        self._progress_source = 0
        self._temp_cwd: str | None = None
        self._last_phase: str | None = None

    def start(self) -> None:
        """Launch croc asynchronously on the GLib main loop."""
        self.canceled = False
        self.success = False
        self.exit_status = -1
        self.error_kind = None
        self._finished = False
        self._waiting_exit = False
        self._lines = []
        self._read_buf = ""
        self._cancellable = Gio.Cancellable()
        try:
            self._launch()
        except GLib.Error as e:
            logger.exception("Failed to start croc")
            self.error_kind = ERROR_SPAWN
            self._on_log(f"Error starting croc: {e.message}")
            self._cleanup()

    def cancel(self) -> None:
        """Terminate the running subprocess."""
        if self.canceled or self._finished:
            return
        self.canceled = True
        self.success = False
        if self._cancellable is not None and not self._cancellable.is_cancelled():
            try:
                self._cancellable.cancel()
            except GLib.Error as e:
                logger.warning("Failed to cancel I/O: %s", e.message)
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
        else:
            try:
                launcher.unsetenv("CROC_SECRET")
            except (AttributeError, GLib.Error):
                pass
        if cwd is not None:
            launcher.set_cwd(cwd)
        # Close stdin so croc never waits on a TTY prompt (GLib has no STDIN_NULL).
        try:
            launcher.set_stdin_file_path(os.devnull)
        except (AttributeError, GLib.Error) as e:
            logger.debug("Could not redirect croc stdin: %s", e)
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
            65536,
            GLib.PRIORITY_LOW,
            self._cancellable,
            self._on_read_chunk,
            None,
        )

    def _on_read_chunk(
        self,
        _stream: Gio.DataInputStream,
        result: Gio.AsyncResult,
        *_user_data: Any,
    ) -> None:
        stream = self._stream
        if stream is None:
            if not self._finished:
                self._wait_for_exit()
            return
        try:
            data = stream.read_bytes_finish(result)
        except GLib.Error:
            if not self._finished:
                self._wait_for_exit()
            return
        if self._finished:
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
            # Progress redraws arrive as a partial CR line; do not parse codes.
            self._handle_line(trailing, complete=False)

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
            if len(self._lines) > _MAX_LOG_LINES:
                self._lines = self._lines[-_MAX_LOG_LINES:]
            self._on_log(stripped)
        self._handle_line(stripped, complete=from_newline or not is_progress)

    def _handle_line(self, line: str, *, complete: bool) -> None:
        phase = detect_transfer_phase(line)
        if phase is not None:
            self._queue_phase(phase)
        fraction = parse_progress_fraction(line)
        if fraction is not None:
            self._queue_progress(fraction)
        if complete:
            kind = classify_croc_error(line)
            if kind is not None:
                self.error_kind = kind

    def _queue_progress(self, fraction: float) -> None:
        if self._on_progress is None:
            return
        self._pending_progress = fraction
        self._ensure_progress_idle()

    def _queue_phase(self, phase: str) -> None:
        if self._on_status is None or phase == self._last_phase:
            return
        self._last_phase = phase
        self._pending_phase = phase
        self._ensure_progress_idle()

    def _ensure_progress_idle(self) -> None:
        if self._progress_source:
            return
        self._progress_source = GLib.timeout_add(
            _PROGRESS_UI_MS, self._flush_progress_ui
        )

    def _flush_progress_ui(self) -> bool:
        self._progress_source = 0
        if self._finished:
            return False
        if self._pending_phase is not None and self._on_status is not None:
            phase = self._pending_phase
            self._pending_phase = None
            self._on_status(phase)
        if self._pending_progress is not None and self._on_progress is not None:
            fraction = self._pending_progress
            self._pending_progress = None
            self._on_progress(fraction)
        return False

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
        self.exit_status, successful = apply_subprocess_status(proc)
        self.success = bool(successful) and not self.canceled
        if not self.success and not self.canceled and self.error_kind is None:
            self.error_kind = ERROR_FAILED
        try:
            self._post_process()
        except Exception:
            logger.exception("Transfer post-process failed")
        self._cleanup()

    def _post_process(self) -> None:
        """Hook for subclasses after the process exits."""

    def _cleanup_temp_cwd(self) -> None:
        if self._temp_cwd:
            shutil.rmtree(self._temp_cwd, ignore_errors=True)
            self._temp_cwd = None

    def _cleanup(self) -> None:
        if self._finished:
            return
        self._finished = True
        if self._progress_source:
            GLib.source_remove(self._progress_source)
            self._progress_source = 0
        if self._pending_phase is not None and self._on_status is not None:
            self._on_status(self._pending_phase)
            self._pending_phase = None
        if self._pending_progress is not None and self._on_progress is not None:
            self._on_progress(self._pending_progress)
            self._pending_progress = None
        self._proc = None
        self._stream = None
        self._cleanup_temp_cwd()
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
        self._code_emitted = False

    def secret_env(self) -> dict[str, str] | None:
        """Env for a custom send code (UNIX croc requires CROC_SECRET, not --code)."""
        custom = (self._settings.get("default_code") or "").strip()
        if not custom:
            return None
        return {"CROC_SECRET": normalize_croc_code(custom)}

    def _build_args(self) -> list[str]:
        s = self._settings
        args = [CROC_BINARY] + build_global_args(
            s, force_yes=True, disable_clipboard=True, ignore_stdin=True
        )
        args += ["send"]
        hash_alg = (s.get("hash") or "").strip()
        if hash_alg:
            args += ["--hash", hash_alg]
        if s.get("zip_folder", False):
            args += ["--zip"]
        if self._text and not self._files:
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
        if self._excluded:
            excludes = ",".join(Path(p).name for p in self._excluded)
            args += ["--exclude", excludes]
        if self._files:
            args += ["--"]
            args += self._files
        return args

    def _handle_line(self, line: str, *, complete: bool) -> None:
        super()._handle_line(line, complete=complete)
        if not complete or self._code_emitted:
            return
        code = extract_send_code(line)
        if code:
            self._code_emitted = True
            self._on_code(code)

    def _launch(self) -> None:
        args = self._build_args()
        self._on_log(f"Running: {format_argv_for_log(args)}")
        self._on_log("Starting croc send")
        self._temp_cwd = tempfile.mkdtemp(prefix="gator-croc-")
        self._spawn(args, env=self.secret_env(), cwd=self._temp_cwd)


class CrocReceiveTransfer(CrocTransfer):
    """Wraps croc receive using ``CROC_SECRET`` (required for non-TTY v10+)."""

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
        self._before: set[str] = set()
        self._saw_file_indicator = False
        self.received_files = False
        self.received_text = False

    def _is_likely_content_line(self, line: str) -> bool:
        return not is_croc_status_line(line)

    def _handle_line(self, line: str, *, complete: bool) -> None:
        super()._handle_line(line, complete=complete)
        if "Receiving file (" in line:
            self._saw_file_indicator = True

    def _launch(self) -> None:
        try:
            os.makedirs(self._save_dir, exist_ok=True)
        except OSError as e:
            self.error_kind = ERROR_PERMISSION
            self._on_log(f"Error creating save folder: {e}")
            self._cleanup()
            return
        if not os.access(self._save_dir, os.W_OK):
            self.error_kind = ERROR_PERMISSION
            self._on_log("Error: save folder is not writable")
            self._cleanup()
            return
        try:
            self._before = set(os.listdir(self._save_dir))
        except OSError:
            self._before = set()
        code = normalize_croc_code(self._code)
        self._code = code
        if not code:
            self.error_kind = ERROR_INVALID_CODE
            self._on_log("Error: no transfer code")
            self._cleanup()
            return
        args = build_receive_args(
            self._settings, force_yes=True, disable_clipboard=True
        )
        self._on_log(f"Running: CROC_SECRET=*** {format_argv_for_log(args)}")
        self._on_log("Receiving transfer")
        self._spawn(args, env=receive_env_for_code(code), cwd=self._save_dir)

    def _post_process(self) -> None:
        if self.canceled or not self.success:
            return
        received_files = False
        try:
            after = set(os.listdir(self._save_dir))
            new_items = after - self._before
            non_text_new = [n for n in new_items if not n.startswith("croc-stdin-")]
            if non_text_new or self._saw_file_indicator:
                received_files = True
        except OSError:
            received_files = self._saw_file_indicator

        text_delivered = False
        if self._check_temp_text_file():
            text_delivered = True

        if not text_delivered and not received_files and not self._saw_file_indicator:
            text_lines = [ln for ln in self._lines if self._is_likely_content_line(ln)]
            text = "\n".join(text_lines).strip()
            if text:
                self._on_text_received(text)
                text_delivered = True

        self.received_text = text_delivered
        self.received_files = received_files
        if received_files and not text_delivered:
            self._on_transfer_complete()

    def _check_temp_text_file(self) -> bool:
        try:
            names = os.listdir(self._save_dir)
        except OSError as e:
            logger.warning("Could not list save directory: %s", e)
            return False
        for filename in names:
            if not filename.startswith("croc-stdin-"):
                continue
            if filename in self._before:
                continue
            temp_file = os.path.join(self._save_dir, filename)
            try:
                with open(temp_file, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                os.remove(temp_file)
            except OSError as e:
                logger.warning("Could not read temp text file: %s", e)
                self._on_log(f"Error reading received text: {e}")
                return False
            text = text.strip()
            if text:
                self._on_text_received(text)
                return True
        return False

"""Unit tests for transfer module (pure logic, no subprocess execution)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import shutil

import pytest

from gator.transfer import (
    ERROR_INVALID_CODE,
    ERROR_PEER,
    ERROR_REFUSED,
    ERROR_RELAY,
    MIN_CROC_CODE_LENGTH,
    CrocReceiveTransfer,
    CrocSendTransfer,
    build_global_args,
    build_receive_args,
    classify_croc_error,
    detect_transfer_phase,
    extract_send_code,
    format_argv_for_log,
    is_croc_status_line,
    is_receive_file_indicator,
    normalize_croc_code,
    parse_progress_fraction,
    receive_env_for_code,
    redact_argv,
    redact_croc_line,
    split_croc_output,
)


def test_parse_progress_fraction():
    assert parse_progress_fraction("Sending  45%") == 0.45
    assert (
        parse_progress_fraction(
            "download.zip  20% |████                | (1.7/8.3 GB, 117 MB/s)"
        )
        == 0.20
    )
    assert parse_progress_fraction("Hashing download.zip  99%") == 0.99
    assert parse_progress_fraction("no progress here") is None
    assert parse_progress_fraction("Save 50% off today") is None
    # croc 11.5 normalized progressbar (20-cell bar + byte count, optional speed/ETA)
    assert (
        parse_progress_fraction(
            "Hashing croc.txt  50% |██████████          | 100/200 B"
        )
        == 0.50
    )
    assert (
        parse_progress_fraction("croc.txt  50% |██████████          | 100/200 B")
        == 0.50
    )
    assert (
        parse_progress_fraction(
            "download.zip  20% |████                | (1.7/8.3 GB, 117 MB/s) [1s:8s]"
        )
        == 0.20
    )
    assert (
        parse_progress_fraction("very-long-filen...  10% |██                  |")
        == 0.10
    )


def test_split_croc_output_handles_carriage_returns():
    chunk = "download.zip  10% |██\rdownload.zip  20% |████\r"
    buf, segments = split_croc_output(chunk)
    assert buf == ""
    assert [s for s, _ in segments] == [
        "download.zip  10% |██",
        "download.zip  20% |████",
    ]
    assert all(not nl for _, nl in segments)


def test_split_croc_output_mixed_newlines_and_carriage_returns():
    chunk = "Code is: abc\nSending (->127.0.0.1:1)\ndownload.zip  5% |█\r"
    buf, segments = split_croc_output(chunk)
    assert buf == ""
    assert segments == [
        ("Code is: abc", True),
        ("Sending (->127.0.0.1:1)", True),
        ("download.zip  5% |█", False),
    ]


def test_split_croc_output_preserves_partial_line():
    buf, segments = split_croc_output("4", "download.zip  ")
    assert buf == "download.zip  4"
    assert segments == []


def test_build_global_args_basic():
    s = {}
    args = build_global_args(s)
    # no extra flags for defaults
    assert "--yes" not in args
    assert "--relay" not in args
    assert "--multicast" not in args
    assert "--curve" not in args


def test_build_global_args_omits_empty_relay():
    args = build_global_args({})
    assert "--relay" not in args
    assert "--relay6" not in args


def test_build_global_args_with_overrides():
    s = {
        "yes": True,
        "overwrite": True,
        "debug": True,
        "relay": "1.2.3.4:9009",
        "pass": "s3cr3t",
        "port": 9999,  # send only
    }
    args = build_global_args(s)
    assert "--yes" in args
    assert "--overwrite" in args
    assert "--debug" in args
    assert "--relay" in args
    assert "1.2.3.4:9009" in args
    assert "--pass" in args and "s3cr3t" in args
    # port not in global
    assert "--port" not in args


def test_send_omits_croc_defaults_when_unset():
    t = CrocSendTransfer(
        settings={},
        files=["/tmp/a.txt"],
        excluded=[],
        text="",
        on_log=lambda m: None,
        on_code=lambda c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "--hash" not in args
    assert "--port" not in args
    assert "--transfers" not in args


def test_send_build_args_includes_files_and_code():
    s = {"default_code": "mycode", "git": True}
    t = CrocSendTransfer(
        settings=s,
        files=["/tmp/a.txt", "/tmp/b", "/tmp/--code"],
        excluded=["/tmp/ignore"],
        text="",
        on_log=lambda m: None,
        on_code=lambda c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "send" in args
    assert "--code" not in args
    assert "--ignore-stdin" in args
    assert args.index("--ignore-stdin") < args.index("send")
    assert "--yes" in args
    assert "--disable-clipboard" in args
    assert t.secret_env() == {"CROC_SECRET": "mycode"}
    assert "--git" in args
    assert "/tmp/a.txt" in args
    assert "--" in args
    assert args.index("--") < args.index("/tmp/--code")
    assert "--exclude" in args
    # exclude uses basename
    assert "ignore" in " ".join(args)


def test_send_text_mode_flag():
    t = CrocSendTransfer(
        settings={},
        files=[],
        excluded=[],
        text="hello world",
        on_log=lambda _m: None,
        on_code=lambda c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "--text" in args
    assert "hello world" in args


@pytest.mark.skipif(shutil.which("croc") is None, reason="croc not installed")
def test_cancel_finishes_transfer():
    from gi.repository import GLib

    finished: list[int] = []

    def on_finished() -> None:
        finished.append(1)

    transfer = CrocSendTransfer(
        settings={"yes": True},
        files=[],
        excluded=[],
        text="cancel-me",
        on_log=lambda _m: None,
        on_code=lambda _c: None,
        on_finished=on_finished,
    )
    loop = GLib.MainLoop()

    def do_cancel() -> bool:
        transfer.cancel()
        return False

    def do_quit() -> bool:
        loop.quit()
        return False

    GLib.timeout_add(300, do_cancel)
    GLib.timeout_add(4000, do_quit)
    transfer.start()
    loop.run()
    assert transfer.canceled
    assert len(finished) == 1


def test_normalize_croc_code():
    assert normalize_croc_code("1234-lion-stop-sofia") == "1234-lion-stop-sofia"
    assert (
        normalize_croc_code("Code is: 1234-lion-stop-sofia") == "1234-lion-stop-sofia"
    )
    assert normalize_croc_code("1234 lion stop sofia") == "1234-lion-stop-sofia"


def test_detect_transfer_phase():
    assert detect_transfer_phase("Hashing download.zip  45%") == "hashing"
    assert detect_transfer_phase("download.zip  20% |██") == "sending"
    assert detect_transfer_phase("Receiving file (foo)  50%") == "receiving"
    assert detect_transfer_phase("waiting for recipient...") == "waiting"
    assert detect_transfer_phase("connecting...") == "connecting"
    assert detect_transfer_phase("Code is: abc") is None
    assert detect_transfer_phase("looking for sender...") == "connecting"
    assert detect_transfer_phase("waiting for sender...") == "waiting"
    assert detect_transfer_phase("authenticating code...") == "connecting"
    assert detect_transfer_phase("opening transfer channels...") == "connecting"
    assert detect_transfer_phase("waiting for file list...") == "waiting"
    assert (
        detect_transfer_phase(
            "Sender detected a transfer interruption. Retrying securely..."
        )
        == "connecting"
    )
    assert (
        detect_transfer_phase("Hashing croc.txt  50% |██████████          | 100/200 B")
        == "hashing"
    )
    assert (
        detect_transfer_phase("croc.txt  50% |██████████          | 100/200 B")
        == "sending"
    )


def test_receive_build_args_respects_yes_pref():
    args = build_receive_args({"yes": False, "relay": ""})
    assert args[0] == "croc"
    assert "--relay" not in args
    assert "--yes" not in args
    assert "--ignore-stdin" in args


def test_receive_build_args_with_yes():
    args = build_receive_args({"yes": True})
    assert "--yes" in args
    assert "abc-code" not in args


def test_receive_env_for_code():
    env = receive_env_for_code("Code is: 1234 test code")
    assert env == {"CROC_SECRET": "1234-test-code"}


def test_is_croc_status_line_filters_cli_output():
    assert is_croc_status_line("connecting...")
    assert is_croc_status_line("securing channel...")
    assert is_croc_status_line("Accept 'wg0.conf_ivpn' (303 B)? (Y/n)")
    assert is_croc_status_line("Receiving (<-83.109.115.4:35166)")
    assert is_croc_status_line("On UNIX systems, to receive with croc you either need")
    assert not is_croc_status_line("hello from sender")
    assert not is_croc_status_line("Line one of a note")
    assert is_croc_status_line("looking for sender...")
    assert is_croc_status_line("authenticating code...")
    assert is_croc_status_line("opening transfer channels...")
    assert is_croc_status_line("On the other computer, run:")
    assert is_croc_status_line("Receiving 'sample.txt' (12 B)")
    assert is_croc_status_line("Sending (198.51.100.10->203.0.113.20)")
    assert is_croc_status_line("A newer croc version is available: v11.5.3")
    assert is_croc_status_line("Already up to date: 'test'")
    assert is_croc_status_line("No files transferred.")


def test_receive_transfer_construction():
    # Just ensure it can be built; run() would start threads+proc
    t = CrocReceiveTransfer(
        settings={},
        code="abc123",
        save_dir="/tmp",
        on_log=lambda m: None,
        on_text_received=lambda t: None,
        on_transfer_complete=lambda: None,
        on_finished=lambda: None,
    )
    assert t._code == "abc123"
    assert not t.canceled


def test_redact_argv_hides_secrets():
    redacted = redact_argv(
        ["croc", "--pass", "s3cr3t", "--text", "hello world", "send"]
    )
    assert "s3cr3t" not in redacted
    assert "hello world" not in redacted
    assert "***" in redacted
    logged = format_argv_for_log(["croc", "--pass", "s3cr3t", "send", "--text", "note"])
    assert "s3cr3t" not in logged
    assert "note" not in logged


def test_extract_send_code_case_insensitive():
    assert extract_send_code("Code is: 1234-lion-stop-sofia") == "1234-lion-stop-sofia"
    assert extract_send_code("code is: abc-def") == "abc-def"
    assert extract_send_code("connecting...") is None
    assert extract_send_code("  croc dent-ounce-fend") == "dent-ounce-fend"
    assert (
        extract_send_code("https://getcroc.com/?code=dent-ounce-fend")
        == "dent-ounce-fend"
    )
    assert (
        extract_send_code("  croc --relay 127.0.0.1:9 --pass s3cr3t barn-boxer-atom")
        == "barn-boxer-atom"
    )
    assert (
        extract_send_code("  croc film-alibi-jet (code copied to clipboard)")
        == "film-alibi-jet"
    )
    assert extract_send_code("croc send file.txt") is None
    assert extract_send_code("On the other computer, run:") is None


def test_classify_croc_error():
    assert classify_croc_error("code is invalid") == ERROR_INVALID_CODE
    assert classify_croc_error("peer disconnected") == ERROR_PEER
    assert classify_croc_error("refusing files") == ERROR_REFUSED
    assert classify_croc_error("could not connect to relay") == ERROR_RELAY
    assert classify_croc_error("Sending 10%") is None
    assert (
        classify_croc_error("code is too short (must be at least 6 characters)")
        == ERROR_INVALID_CODE
    )
    assert classify_croc_error("password mismatch") == ERROR_INVALID_CODE
    assert classify_croc_error("refused files") == ERROR_REFUSED
    assert (
        classify_croc_error("could not connect to : found no relay addresses")
        == ERROR_RELAY
    )
    assert (
        classify_croc_error("transfer disconnected after 10 reconnect attempts")
        == ERROR_PEER
    )
    assert classify_croc_error("could not secure channel") == ERROR_PEER


def test_build_global_args_rename_not_overwrite():
    args = build_global_args({"rename": True, "overwrite": False})
    assert "--rename" in args
    assert "--overwrite" not in args
    args = build_global_args({"rename": True, "overwrite": True})
    assert "--overwrite" in args
    assert "--rename" not in args


def test_receive_force_yes_and_clipboard():
    args = build_receive_args({"yes": False}, force_yes=True, disable_clipboard=True)
    assert "--yes" in args
    assert "--disable-clipboard" in args


def test_empty_custom_code_has_no_secret_env():
    t = CrocSendTransfer(
        settings={"default_code": ""},
        files=["/tmp/a.txt"],
        excluded=[],
        text="",
        on_log=lambda _m: None,
        on_code=lambda _c: None,
        on_finished=lambda: None,
    )
    assert t.secret_env() is None
    assert "--code" not in t._build_args()


def test_normalize_croc_code_from_croc_11_5_paste():
    banner = (
        "On the other computer, run:\n"
        "  croc dent-ounce-fend\n"
        "\n"
        "Or open:\n"
        "  https://getcroc.com/?code=dent-ounce-fend\n"
    )
    assert normalize_croc_code(banner) == "dent-ounce-fend"
    assert (
        normalize_croc_code("https://getcroc.com/?code=film-alibi-jet")
        == "film-alibi-jet"
    )
    assert normalize_croc_code("  croc --relay 1.2.3.4:9009 secret-phrase") == (
        "secret-phrase"
    )


def test_is_receive_file_indicator():
    assert is_receive_file_indicator("Receiving file (foo.txt)")
    assert is_receive_file_indicator("Receiving 'sample.txt' (12 B)")
    assert is_receive_file_indicator('Receiving "notes.md" (1.2 KB)')
    assert not is_receive_file_indicator("Receiving (<-83.109.115.4:35166)")
    assert not is_receive_file_indicator("Receiving (198.51.100.10<-203.0.113.20)")
    assert not is_receive_file_indicator("Receiving 'croc-stdin-abc123' (11 B)")
    assert not is_receive_file_indicator("connecting...")


def test_redact_croc_line_hides_pass_in_instructions():
    line = "  croc --relay 127.0.0.1:9 --pass s3cr3t barn-boxer-atom"
    redacted = redact_croc_line(line)
    assert "s3cr3t" not in redacted
    assert "--pass ***" in redacted
    assert "barn-boxer-atom" in redacted


def test_maybe_emit_known_custom_code():
    codes: list[str] = []
    t = CrocSendTransfer(
        settings={"default_code": "my-secret-code"},
        files=["/tmp/a.txt"],
        excluded=[],
        text="",
        on_log=lambda _m: None,
        on_code=codes.append,
        on_finished=lambda: None,
    )
    t._maybe_emit_known_code()
    assert codes == ["my-secret-code"]
    t._maybe_emit_known_code()
    assert codes == ["my-secret-code"]


def test_build_global_args_socks5_and_connect():
    args = build_global_args(
        {"socks5": "127.0.0.1:9050", "connect": "http://proxy:8080"}
    )
    assert "--socks5" in args and "127.0.0.1:9050" in args
    assert "--connect" in args and "http://proxy:8080" in args


def test_min_croc_code_length_matches_croc():
    assert MIN_CROC_CODE_LENGTH == 6


def test_split_croc_output_receive_status_redraws():
    chunk = (
        "connecting...\rlooking for sender...\rwaiting for sender...\r"
        "                     \r"
    )
    buf, segments = split_croc_output(chunk)
    assert buf == ""
    texts = [s for s, _ in segments]
    assert "connecting..." in texts
    assert "looking for sender..." in texts
    assert "waiting for sender..." in texts
    assert all(not nl for _, nl in segments)


def test_gui_send_keeps_yes_and_ignore_stdin():
    t = CrocSendTransfer(
        settings={"yes": False},
        files=["/tmp/a.txt"],
        excluded=[],
        text="",
        on_log=lambda _m: None,
        on_code=lambda _c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "--yes" in args
    assert "--ignore-stdin" in args
    assert "--code" not in args


def test_gui_receive_keeps_yes_and_ignore_stdin():
    args = build_receive_args({"yes": False}, force_yes=True, disable_clipboard=True)
    assert "--yes" in args
    assert "--ignore-stdin" in args
    assert "--code" not in args

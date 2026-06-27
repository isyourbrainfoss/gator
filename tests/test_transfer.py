"""Unit tests for transfer module (pure logic, no subprocess execution)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gator.transfer import (
    CrocReceiveTransfer,
    CrocSendTransfer,
    build_global_args,
    build_receive_args,
    detect_transfer_phase,
    normalize_croc_code,
    parse_progress_fraction,
    receive_env_for_code,
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
        files=["/tmp/a.txt", "/tmp/b"],
        excluded=["/tmp/ignore"],
        text="",
        on_log=lambda m: None,
        on_code=lambda c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "send" in args
    assert "--code" in args and "mycode" in args
    assert "--git" in args
    assert "/tmp/a.txt" in args
    assert "--exclude" in args
    # exclude uses basename
    assert "ignore" in " ".join(args)


def test_send_text_mode_flag():
    t = CrocSendTransfer(
        settings={},
        files=[],
        excluded=[],
        text="hello world",
        on_log=print,
        on_code=lambda c: None,
        on_finished=lambda: None,
    )
    args = t._build_args()
    assert "--text" in args
    assert "hello world" in args


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
    GLib.timeout_add(300, lambda: (transfer.cancel(), False))
    GLib.timeout_add(4000, lambda: (loop.quit(), False))
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
    assert detect_transfer_phase("Code is: abc") is None


def test_receive_build_args_respects_yes_pref():
    args = build_receive_args({"yes": False, "relay": ""})
    assert args[0] == "croc"
    assert "--relay" not in args
    assert "--yes" not in args
    assert len(args) == 1


def test_receive_build_args_with_yes():
    args = build_receive_args({"yes": True})
    assert "--yes" in args
    assert "abc-code" not in args


def test_receive_env_for_code():
    env = receive_env_for_code("Code is: 1234 test code")
    assert env == {"CROC_SECRET": "1234-test-code"}


def test_is_likely_content_rejects_croc_unix_help():
    from gator.transfer import CrocReceiveTransfer

    t = CrocReceiveTransfer(
        settings={},
        code="x",
        save_dir="/tmp",
        on_log=lambda _m: None,
        on_text_received=lambda _t: None,
        on_transfer_complete=lambda: None,
        on_finished=lambda: None,
    )
    line = "On UNIX systems, to receive with croc you either need"
    assert not t._is_likely_content_line(line)


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

"""Unit tests for transfer module (pure logic, no subprocess execution)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gator.transfer import CrocReceiveTransfer, CrocSendTransfer, build_global_args


def test_build_global_args_basic():
    s = {}
    args = build_global_args(s)
    # no extra flags for defaults
    assert "--yes" not in args
    assert "--relay" not in args  # default is used inside croc


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

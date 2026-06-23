# Gator – Refactoring & Production Readiness Tasks

This document tracks the refactoring work needed to make Gator production-ready
(renamed from the former "Croc GUI" project)
for Flathub submission. The original single-file app had several critical bugs and
HIG violations that have been systematically addressed.

## Session Summary

**Session 1:** Fixed all P0 critical bugs (6 items)  
**Session 2:** Completed most P1-P3 items (9 additional items)  
**Session 3:** Completed final P1 item (1 additional item)  
**Session 4:** Completed remaining P2/P3 + modules + tests + meson/flatpak (6+ items)

**Total progress:** 23/25 items completed (92%)  
**Remaining:** 2 stretch items (cancelled as out-of-scope for this pass)

## Critical Fixes (P0) — completed in session 1

- [x] **Unified `_build_global_args()`** – replaced the two divergent implementations
  (`get_global_args()` for receive vs. inline block for send). Receive was silently
  ignoring all user settings except relay and password. Now both paths share one
  method.
- [x] **Thread-safe subprocess handles** – renamed `send_proc`/`receive_proc` to
  private attributes, protected reads/writes with `threading.Lock`, closed stdout
  pipes in `finally` blocks, cleared proc references after `wait()`.
- [x] **`Adw.HeaderBar` on modal windows** – `on_add_text` and `show_received_text`
  now use `Adw.ToolbarView` + `Adw.HeaderBar`, giving them a CSD close button on
  Wayland.
- [x] **`Adw.AboutDialog` with fallback** – replaced deprecated `Adw.AboutWindow`
  with `Adw.AboutDialog` (libadwaita ≥ 1.5); falls back to `Adw.AboutWindow` on
  older runtimes.
- [x] **Removed `Adw.init()`** – unnecessary with `Adw.Application`; deprecated in
  libadwaita 1.7+ (GNOME 50 - freshest).
- [x] **Replaced silent `except: pass` with logging** – `load_settings`,
  `save_settings`, QR generation, clipboard paste, QR scan, and the folder-open
  handler all now log warnings/errors and surface failures to the user via toasts
  where appropriate. `logging.basicConfig` wired at entry point.

---

## High Priority (P1) — completed

- [x] **Replace `Gtk.Window` preferences with `Adw.PreferencesDialog`** –
  replaced the manual `Gtk.Window` + `Adw.HeaderBar` with proper `Adw.PreferencesDialog`
  (falling back to the old approach on libadwaita < 1.5). Added helper methods
  `_make_switch_row()` and `_make_entry_row()` to reduce code duplication.
- [x] **Add receive-side `--yes`/`--overwrite` preference rows** – previously 
  hardcoded as `--yes --overwrite`, now exposed as "Automatically accept incoming 
  transfers" and "Overwrite existing files without prompt" toggles in the Receiving 
  section.

## High Priority (P1) — completed

- [x] **Extract `transfer.py`** – created `CrocTransfer` base class with
  `CrocSendTransfer` and `CrocReceiveTransfer` subclasses. All subprocess/thread
  logic moved out of the main Application class. Callbacks use `GLib.idle_add`
  for main-loop dispatch. Settings-only dependency enables unit testing without
  GTK. Reduced `app.py` by ~150 lines.

---

## Medium Priority (P2) — completed

- [x] **Add constants block** – extracted `APP_ID`, `CROC_BINARY`, `DEFAULT_PORT`,
  `DEFAULT_TRANSFERS`, `DEFAULT_MULTICAST`, `DEFAULT_RELAY`, `DEFAULT_RELAY6`,
  `CODE_IS_PREFIX`, `APP_NAME`, and `APP_VERSION` constants. Threaded references
  throughout the codebase, eliminating 15+ magic strings.
- [x] **Fix `destructive-action` misuse on Exclude button** – changed from
  `destructive-action` to `flat` since exclusions are reversible.
- [x] **Add type annotations and docstrings** – added complete type hints and
  docstrings to all public methods. Imported `from __future__ import annotations`
  and `typing.Any` for forward compatibility.

## Medium Priority (P2) — completed

- [x] **Extract `settings.py`** – centralise config load/save with validation.
  JSON remains the runtime store; GSettings schema stub + meson support added
  as preparation for Flatpak migration.
- [x] **Extract `send_page.py` and `receive_page.py`** – UI construction moved
  into widget subclasses (SendPage / ReceivePage). Controller state and handlers
  remain in Gator for compatibility.
- [x] **Improve received-text detection** – replaced brittle "Receiving (<-"
  prefix + progress filter with:
  - directory snapshot before/after to decide file vs text
  - relaxed content-line collector (no reliance on exact marker string)
  - always fall back to croc-stdin-* temp file
  - added _is_likely_content_line helper.

---

## Low Priority (P3) — completed

- [x] **`.desktop` file** (`data/org.gator.Gator.desktop`) – application launcher
  with proper categories, keywords, MIME type, and GNOME integration.
- [x] **AppStream metainfo** (`data/org.gator.Gator.metainfo.xml`) – complete
  metainfo with description, screenshots, release notes, content rating, and
  all required Flathub fields.
- [x] **SVG app icon stub** (`data/org.gator.Gator.svg`) – placeholder icon with
  transfer arrows. Should be replaced with a proper HIG-compliant design.
- [x] **Python packaging** (`pyproject.toml`) – complete packaging metadata with
  optional dependencies, development tools, and entry points.

## Low Priority (P3) — completed

- [x] **Meson build system** – `meson.build` + data launcher template. Installs
  desktop file, metainfo, scalable icon, gschema, Python sources.
- [x] **Flatpak manifest** (`org.gator.Gator.yml`) – bundles croc (Go build
  module) + GUI. Uses GNOME 50 runtime.
- [x] **Unit tests** – Added `tests/test_settings.py`, `test_transfer.py`,
  `test_qr.py`. Pure logic only (no GTK). Run with `pytest`.
- [x] **QR module** – extracted inline QR bits to `qr.py` (optional deps).

---

## Stretch / Future (P4) — pending

- [ ] **Replace `subprocess.Popen` + threads with `Gio.Subprocess`** – integrates
  with the GLib main loop natively, removing the need for manual threads and
  `GLib.idle_add` for stdout reading.
- [ ] **Progress reporting** – parse croc's progress output and drive a
  `Gtk.ProgressBar` instead of a spinner.
- [ ] **Resume / history** – store a transfer log with timestamps, file names, and
  codes in `~/.local/share/gator/` (or `~/.config/gator/`).
- [x] **Drag-and-drop to receive** – accept a dropped image file on the receive
  page (via ReceivePage) and run QR scan (bonus P4 item completed).
- [ ] (remaining P4) Replace subprocess with Gio.Subprocess, progress bars, history.

(Three P2 + three P3 + 1 P4 bonus completed. 2 stretch items remain.)

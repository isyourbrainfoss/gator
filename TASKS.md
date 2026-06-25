# Gator – Refactoring & Production Readiness Tasks

Tracks work toward a stable Flatpak release. Most items are done; see **Remaining** at the bottom.

## Status

**25/26 items completed (96%)**

| Priority | Done |
|----------|------|
| P0 Critical | 6/6 |
| P1 High | 3/3 |
| P2 Medium | 6/6 |
| P3 Low | 8/8 |
| P4 Stretch | 2/3 |

## Critical Fixes (P0) — done

- [x] Unified `build_global_args()` for send and receive
- [x] Thread-safe subprocess handles (legacy; superseded by Gio.Subprocess)
- [x] `Adw.HeaderBar` on modal windows
- [x] `Adw.AboutDialog` with fallback
- [x] Removed `Adw.init()`
- [x] Replaced silent `except: pass` with logging

## High Priority (P1) — done

- [x] `Adw.PreferencesDialog` for settings
- [x] Receive-side `--yes` / `--overwrite` preference rows
- [x] Extract `transfer.py` (`CrocSendTransfer` / `CrocReceiveTransfer`)

## Medium Priority (P2) — done

- [x] Constants block in `settings.py`
- [x] Fix `destructive-action` misuse on Exclude button
- [x] Type annotations and docstrings
- [x] Extract `settings.py` with validation and GSettings + JSON fallback
- [x] Extract `send_page.py` and `receive_page.py`
- [x] Improve received-text detection

## Low Priority (P3) — done

- [x] `.desktop` file
- [x] AppStream metainfo
- [x] SVG app icon
- [x] `pyproject.toml` packaging
- [x] Meson build system
- [x] Flatpak manifest (bundles croc v10.4.4)
- [x] Unit tests (`test_settings`, `test_transfer`, `test_qr`, `test_theme`)
- [x] QR module (`qr.py`)

## Stretch (P4)

- [x] **Gio.Subprocess** – `transfer.py` uses async `Gio.Subprocess` + chunk reads (no worker threads)
- [x] **Progress reporting** – parse croc `\r`/`\n` output; drive send/receive progress bars
- [x] **Drag-and-drop to receive** – QR scan from dropped image
- [ ] **Transfer history** – optional log of past codes/files (not planned for v1.x)

## Post-roadmap fixes (v1.5)

- [x] Empty croc defaults (relay, port, hash, etc.) — let croc use its own built-ins
- [x] Legacy relay migration for older saved settings
- [x] Send UI: full-width progress bar, sent-file checkmarks, completion feedback
- [x] GitHub Pages Flatpak repo (x86_64 + aarch64) on every `master` push

## Remaining / optional

- [ ] Transfer history (P4 — defer)
- [ ] Replace placeholder screenshots in metainfo before Flathub submission
- [ ] Flathub submission (optional; GitHub Pages install works without it)

## Distribution notes

- **End users:** install via Flatpak from GitHub Pages (`org.gator.Gator.flatpakref`). No separate croc install; CI builds from `org.gator.Gator.devel.yml` on each push to `master`.
- **Version tags:** optional GitHub Releases (`v1.5`, …) for changelog visibility. Flatpak updates do **not** require a GitHub Release — only a successful Publish Flatpak workflow on `master`.
- **Pinned manifest:** `org.gator.Gator.yml` pins a git tag/commit for reproducible release builds (Flathub-style); keep in sync when tagging.
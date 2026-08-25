# Gator – Agent Guide

## Essential Commands

```bash
# Development setup
pip install -e '.[qr,dev]'

# Run application directly (development)
PYTHONPATH=src python -m gator

# After editable install:
gator

# Flatpak build test (local tree)
flatpak-builder --user --install-deps-from=flathub --force-clean build-dir org.gator.Gator.devel.yml
flatpak run org.gator.Gator

# Release manifest (fetches from GitHub)
flatpak-builder --user --install-deps-from=flathub --force-clean build-dir org.gator.Gator.yml

# CI publishes to GitHub Pages via .github/workflows/flatpak-publish.yml

# Code quality (all must pass)
black .
ruff check .
python3 -m mypy --ignore-missing-imports --no-error-summary src/gator/ || echo "(mypi notes for gi + optional strictness are pre-existing)"

# Installation testing
pip install -e .
gator

## Architecture

- **Modular source**: `src/gator/` contains the GTK application (split from the original single-file prototype)
- **Extracted module**: `transfer.py` wraps `croc` with `Gio.Subprocess` async I/O on the GLib main loop (no worker threads)
- **External dependency**: Requires `croc` binary in PATH for pip/source runs; Flatpak bundles croc
- **Optional QR support**: Install with `[qr]` extra for QR code generation/scanning

## Key Dependencies

- **Python 3.10+** with PyGObject >= 3.42
- **GTK 4** and **libadwaita 1.7+** (newer versions use `Adw.PreferencesDialog` vs fallback; Flatpak targets GNOME 50)
- **croc binary** must be available in PATH at runtime

## Development Workflow

1. **Code style**: Black (88 chars) → Ruff linting → MyPy type checking
2. **No git hooks**: Run quality checks manually before commits
3. **Main-loop I/O**: croc runs as `Gio.Subprocess`; drain stdout asynchronously on the GLib main loop (no daemon worker threads)

## Critical Notes

- **Libadwaita version compatibility**: Prefer `Adw.AboutDialog` / `Adw.PreferencesDialog` with fallbacks where the API is missing; recommended runtime is GNOME 50 (libadwaita 1.7+)
- **Subprocess lifecycle**: Cancel with `CrocTransfer.cancel()`; always finish outstanding Gio async reads; treat `wait_finish` as a boolean, not an exit code (`get_exit_status` / `get_successful`)
- **Settings format**: GSettings in Flatpak (`org.gator.Gator.gschema.xml`); JSON fallback in `~/.config/gator/` for dev/pip runs
- **QR dependencies are optional**: Application degrades gracefully without PIL/pyzbar
- **UNIX custom send codes**: Pass the phrase in `CROC_SECRET`, never `--code` (croc v10+ exits on UNIX if `--code` is set without the env var)

## Current Status

See `TASKS.md` for the roadmap. Core app, Flatpak, and transfer reliability (honest success/fail, croc 11.3.2) are in tree. Optional later: Flathub, transfer history, real screenshots.

## Testing Strategy

- **Unit tests**: `tests/test_transfer.py`, `test_settings.py`, `test_qr.py`, `test_theme.py` (no GTK widgets except Gio subprocess in the cancel test)
- **Manual testing**: Test on GNOME 50 (freshest) and older with fallbacks, test QR optional dependencies, verify Flatpak build with current runtime
- **Integration**: Test croc binary integration with various file types and sizes
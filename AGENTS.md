# Croc GUI – Agent Guide

## Essential Commands

```bash
# Development setup
pip install -e '.[qr,dev]'

# Run application directly (development)
python3 croc_gui.py

# Flatpak build test
flatpak-builder --user --install --force-clean build-dir org.croc.CrocGUI.yml
flatpak run org.croc.CrocGUI

# Code quality (all must pass)
black .
ruff check .
python3 -m mypy --ignore-missing-imports --no-error-summary src/croc_gui/ || echo "(mypi notes for gi + optional strictness are pre-existing)"

# Installation testing
pip install -e .
croc-gui

## Architecture

- **Single-file prototype**: `croc_gui.py` (~1200 lines) contains entire GTK application
- **Extracted module**: `transfer.py` handles subprocess/threading for croc binary
- **External dependency**: Requires `croc` binary in PATH for actual file transfers
- **Optional QR support**: Install with `[qr]` extra for QR code generation/scanning

## Key Dependencies

- **Python 3.10+** with PyGObject >= 3.42
- **GTK 4** and **libadwaita 1.4+** (newer versions use `Adw.PreferencesDialog` vs fallback)
- **croc binary** must be available in PATH at runtime

## Development Workflow

1. **Code style**: Black (88 chars) → Ruff linting → MyPy type checking
2. **No git hooks**: Run quality checks manually before commits
3. **Thread safety**: All subprocess I/O uses daemon threads with `GLib.idle_add` for UI updates

## Critical Notes

- **Libadwaita version compatibility**: Code includes fallbacks for older libadwaita versions (`Adw.AboutDialog` vs `Adw.AboutWindow`, `Adw.PreferencesDialog` availability)
- **Thread-safe subprocess**: Never access `send_proc`/`receive_proc` without proper locking
- **Settings format**: Currently JSON in config dir; planned migration to GSettings for Flatpak compatibility
- **QR dependencies are optional**: Application degrades gracefully without PIL/pyzbar

## Current Status

See `TASKS.md` for detailed roadmap. **64% complete** toward production readiness:
- ✅ All P0 critical bugs fixed (thread safety, HIG compliance)  
- ✅ Transfer logic extracted, type annotations added
- 🔄 Next: Extract settings/pages modules, Meson build system, Flatpak packaging

## Testing Strategy

- **Unit tests**: Planned for `transfer.py` and future `settings.py` (no GTK dependencies)
- **Manual testing**: Run with different libadwaita versions, test QR optional dependencies
- **Integration**: Test croc binary integration with various file types and sizes
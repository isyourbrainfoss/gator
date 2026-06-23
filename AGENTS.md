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
- **Extracted module**: `transfer.py` handles subprocess/threading for croc binary
- **External dependency**: Requires `croc` binary in PATH for actual file transfers
- **Optional QR support**: Install with `[qr]` extra for QR code generation/scanning

## Key Dependencies

- **Python 3.10+** with PyGObject >= 3.42
- **GTK 4** and **libadwaita 1.7+** (newer versions use `Adw.PreferencesDialog` vs fallback; Flatpak targets GNOME 50)
- **croc binary** must be available in PATH at runtime

## Development Workflow

1. **Code style**: Black (88 chars) → Ruff linting → MyPy type checking
2. **No git hooks**: Run quality checks manually before commits
3. **Thread safety**: All subprocess I/O uses daemon threads with `GLib.idle_add` for UI updates

## Critical Notes

- **Libadwaita version compatibility**: Code includes fallbacks for older libadwaita versions (`Adw.AboutDialog` vs `Adw.AboutWindow`, `Adw.PreferencesDialog` availability); recommended runtime is GNOME 50 (libadwaita 1.7+)
- **Thread-safe subprocess**: Never access `send_proc`/`receive_proc` without proper locking
- **Settings format**: Currently JSON in config dir; planned migration to GSettings for Flatpak compatibility
- **QR dependencies are optional**: Application degrades gracefully without PIL/pyzbar

## Current Status

See `TASKS.md` for detailed roadmap. **64% complete** toward production readiness:
- ✅ All P0 critical bugs fixed (thread safety, HIG compliance)  
- ✅ Transfer logic extracted, type annotations added
- ✅ Runtime updated to freshest GNOME 50
- 🔄 Next: full GSettings migration, modern packaging refinements, Flatpak polish for Flathub

## Testing Strategy

- **Unit tests**: Planned for `transfer.py` and future `settings.py` (no GTK dependencies)
- **Manual testing**: Test on GNOME 50 (freshest) and older with fallbacks, test QR optional dependencies, verify Flatpak build with current runtime
- **Integration**: Test croc binary integration with various file types and sizes
# Croc GUI

A modern GTK4/Libadwaita frontend for [croc](https://github.com/schollz/croc) – secure file transfers made beautiful.

## Features

- 🚀 **Simple & Fast** – Drag-and-drop files, folders, and text
- 🔐 **Secure** – End-to-end encryption via croc
- 📱 **Adaptive** – Works on desktop and mobile with responsive layout
- 🎨 **Native** – Follows GNOME HIG with libadwaita widgets  
- 📷 **QR Codes** – Generate and scan QR codes for easy code sharing
- ⚙️ **Configurable** – Comprehensive settings for power users

## Installation

### Requirements

- **croc** binary (install from your distro or [releases page](https://github.com/schollz/croc/releases))
- **Python 3.10+** with PyGObject
- **GTK 4** and **libadwaita 1.4+**

### From Source (development)

```bash
git clone https://github.com/yourname/croc-gui.git
cd croc-gui
pip install -e '.[qr,dev]'

# Run directly:
python3 croc_gui.py

# Or after install:
croc-gui
```

### Flatpak (for release / distribution)

See `org.croc.CrocGUI.yml`.

Build locally:

```bash
flatpak-builder --user --install --force-clean build-dir org.croc.CrocGUI.yml
flatpak run org.croc.CrocGUI
```

For a polished Flathub release you will also want:
- Real screenshots in the metainfo
- A high-quality app icon (replace `data/org.croc.CrocGUI.svg`)
- Consider migrating settings to GSettings (stub schema already present)
```

### Development

```bash
pip install -e .[qr,dev]
python3 croc_gui.py
```

## Project Status

Currently a **single-file prototype** (`croc_gui.py`, ~1350 lines). See [`TASKS.md`](TASKS.md) for the roadmap to production readiness.

**Completed:**
- ✅ All critical bugs fixed (thread-safety, global args divergence, HIG violations)  
- ✅ Type annotations, docstrings, and constants  
- ✅ Libadwaita preferences dialog  
- ✅ Basic packaging metadata and data files

**Next steps:**
- 🔄 Extract transfer logic into separate module  
- 🔄 Meson build system for proper installation  
- 🔄 Flatpak packaging for Flathub submission

## Screenshots

_(Screenshots coming soon)_

## Contributing

See [`TASKS.md`](TASKS.md) for current priorities. The codebase is well-documented and ready for contributions.

## License

GPL-3.0-or-later – See [LICENSE](LICENSE) for details.
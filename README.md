# Gator

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
- **GTK 4** and **libadwaita 1.7+** (GNOME 50 runtime - freshest)

### From Source (development)

```bash
git clone https://github.com/isyourbrainfoss/gator.git
cd gator
pip install -e '.[qr,dev]'

# Run directly (no install needed):
PYTHONPATH=src python -m gator

# Or after install (recommended):
gator
```

### Flatpak (recommended for end users)

Gator bundles the `croc` binary inside the Flatpak — no separate croc install needed.

**Local development build** (uses your working tree):

```bash
flatpak-builder --user --install-deps-from=flathub \
  --force-clean build-dir org.gator.Gator.devel.yml
flatpak run org.gator.Gator
```

**Release build** (fetches source from GitHub, same as Flathub):

```bash
flatpak-builder --user --install-deps-from=flathub \
  --force-clean build-dir org.gator.Gator.yml
flatpak run org.gator.Gator
```

**Install from Flathub** (once published — no git required):

```bash
flatpak install flathub org.gator.Gator
flatpak run org.gator.Gator
```

#### Flathub submission checklist

1. Merge `rename-to-gator` into `main` and push to GitHub.
2. Tag the release and update the pinned `tag` + `commit` in `org.gator.Gator.yml`:
   ```bash
   git tag v1.4
   git push origin v1.4
   ```
3. Add real screenshots under `data/screenshots/` (1600×900 or 1200×675 PNG) — URLs in `data/org.gator.Gator.metainfo.xml` must resolve.
4. Replace the placeholder icon (`data/org.gator.Gator.svg`) with a HIG-compliant design.
5. Set a real `update_contact` email in the metainfo file.
6. Build and lint locally:
   ```bash
   flatpak install -y flathub org.flatpak.Builder
   flatpak run --command=flathub-build org.flatpak.Builder --install org.gator.Gator.yml
   flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest org.gator.Gator.yml
   ```
7. Fork [flathub/flathub](https://github.com/flathub/flathub), branch from `new-pr`, add `org.gator.Gator.yml` (copy from this repo), open a PR titled **"Add org.gator.Gator"** against the `new-pr` base branch.
8. Address review comments; comment `bot, build` on the PR to trigger a test build.
9. After merge, Flathub hosts builds — users install with `flatpak install flathub org.gator.Gator`.

See [Flathub submission docs](https://docs.flathub.org/docs/for-app-authors/submission).

### Development

```bash
pip install -e .[qr,dev]
python3 -m gator  # or the installed gator command
```

## Project Status

The UI code has been split into modules under `src/gator/`. See [`TASKS.md`](TASKS.md) for the roadmap.

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
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

#### Install from the GitHub-hosted repository (no git, no Flathub)

GitHub Actions builds a Flatpak repository and publishes it to GitHub Pages.
Users only need `flatpak` and the Flathub *runtime* (pulled automatically as a dependency).

**One-time setup** (repo maintainer):

1. Enable **Settings → Pages → Source: GitHub Actions** (requires a **public** repository on the free GitHub plan).
2. Wait for the [Publish Flatpak](.github/workflows/flatpak-publish.yml) workflow to finish after a push to `master`.

After Pages is live:

```bash
# Add the Gator remote (unsigned community repo — normal for self-hosted builds)
flatpak remote-add --user --if-not-exists --no-gpg-verify --from \
  https://isyourbrainfoss.github.io/gator/gator.flatpakrepo gator

# Install (also pulls org.gnome.Platform from Flathub as a runtime dependency)
flatpak install --user gator org.gator.Gator
flatpak run org.gator.Gator
```

Alternative one-liner using the `.flatpakref` file in this repo:

```bash
flatpak install --user --no-gpg-verify --from \
  https://raw.githubusercontent.com/isyourbrainfoss/gator/master/org.gator.Gator.flatpakref
```

Updates later: `flatpak update --user org.gator.Gator`

**Private repository?** GitHub Pages is not available on the free plan for private repos.
Download the `.flatpak` bundle from the latest [Actions workflow run](https://github.com/isyourbrainfoss/gator/actions) (Artifacts), then:

```bash
flatpak install --user ./org.gator.Gator.flatpak
```

Or make the repository public to use the Pages-hosted remote above.

#### Publishing new builds

Push to the default branch on GitHub (`main` or `master`). That triggers a rebuild and
updates the Pages-hosted repository automatically. No git required on the user's machine.

If your local rename work is on a feature branch, push it to GitHub's default branch, e.g.:

```bash
git push origin rename-to-gator:master
```

#### Local development build (uses your working tree)

```bash
flatpak-builder --user --install-deps-from=flathub \
  --force-clean build-dir org.gator.Gator.devel.yml
flatpak run org.gator.Gator
```

#### Optional: Flathub

Flathub is independent and optional. If you submit there later, users would run
`flatpak install flathub org.gator.Gator`. The self-hosted GitHub Pages repo works without it.

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
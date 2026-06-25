# Gator

GTK4/Libadwaita app for [croc](https://github.com/schollz/croc) — send files, folders, and text with end-to-end encryption.

**Flatpak includes croc** — no separate croc install needed.

## Install (Flatpak)

Requires [Flatpak](https://flatpak.org/) and the Flathub remote (for the GNOME runtime):

```bash
flatpak remote-add --user --if-not-exists flathub \
  https://dl.flathub.org/repo/flathub.flatpakrepo

flatpak install --user --from \
  https://raw.githubusercontent.com/isyourbrainfoss/gator/master/org.gator.Gator.flatpakref

flatpak run org.gator.Gator
```

Updates: `flatpak update --user org.gator.Gator`

Builds are published for **x86_64** and **aarch64** from [GitHub Pages](https://isyourbrainfoss.github.io/gator/).

## Run from source

For development only. You need **croc** on your `PATH`, plus Python 3.10+, PyGObject, GTK 4, and libadwaita 1.7+.

```bash
git clone https://github.com/isyourbrainfoss/gator.git
cd gator
pip install -e '.[qr,dev]'
gator
```

## Build Flatpak locally

```bash
flatpak-builder --user --install-deps-from=flathub --force-clean \
  build-dir org.gator.Gator.devel.yml
flatpak run org.gator.Gator
```

## Contributing

See [`TASKS.md`](TASKS.md) for the roadmap.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
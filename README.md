# Gator

> **Note**
> This is very experimental. Assume nothing here is written, or necessarily read through or fully understood, by a human unless stated, and that includes this text. Use it at your own risk, but you're encouraged to reuse any parts you find useful. The human work here is mainly ideas, testing in reality, and persistence with a vision.

GTK4/Libadwaita app for [croc](https://github.com/schollz/croc) — send files, folders, and text with end-to-end encryption. Flatpak currently bundles **croc 11.6.6**.

**Flatpak includes croc** — no separate croc install needed.

## Install (Flatpak)

Gator is published in the signed [isyourbrainfoss Flatpak repository](https://isyourbrainfoss.github.io/flatpak/)
for **x86_64** and **aarch64** (branch `stable`). Runtimes come from Flathub automatically.

```bash
flatpak remote-add --user --if-not-exists isyourbrainfoss \
  https://isyourbrainfoss.github.io/flatpak/isyourbrainfoss.flatpakrepo
flatpak install --user isyourbrainfoss org.gator.Gator
flatpak run org.gator.Gator
```

Or in one step: `flatpak install --user --from https://isyourbrainfoss.github.io/flatpak/org.gator.Gator.flatpakref`

Updates: `flatpak update`, or GNOME Software / KDE Discover / Bazaar.

### Moving from the old unsigned repo

The old repository at https://isyourbrainfoss.github.io/gator/ (remote `gator`, `--no-gpg-verify`,
branch `master`) keeps getting builds until **2027-01-15**, then it stops. Switch now (your settings
in `~/.var/app/org.gator.Gator` are kept):

```bash
flatpak remote-add --user --if-not-exists isyourbrainfoss \
  https://isyourbrainfoss.github.io/flatpak/isyourbrainfoss.flatpakrepo
flatpak install --user --reinstall isyourbrainfoss org.gator.Gator
flatpak remote-delete --user gator
```

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

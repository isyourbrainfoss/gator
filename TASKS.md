# Gator – Task list

## Status: ~98% production-ready

Core app, Flatpak, and CI are done. **You:** proper app icon + real screenshots. **Optional later:** Flathub, transfer history.

---

## Done

### Core (P0–P3)
- Modular GTK4/libadwaita app (`app`, `window`, pages, `transfer`, `settings`, `preferences`)
- `Gio.Subprocess` transfers with `\r`/`\n` progress parsing
- GSettings + JSON fallback; empty croc defaults + legacy relay migration
- Flatpak bundles croc v10.4.4; GitHub Pages repo (x86_64 + aarch64)
- Meson, desktop, metainfo, CI (black/ruff/mypy/pytest)
- Unit tests: settings, transfer, qr, theme

### UX (v1.5)
- Send: full-width progress, sent checkmarks, completion feedback
- Receive: same completion pattern (status icon, folder row success state)
- Transfer phase labels (Hashing / Sending / Receiving)
- `GATOR_LOG=1` for debug logging

### Polish (v1.5.1 — in repo)
- [x] Receive respects `--yes` preference (no forced flag)
- [x] Default `yes=true` for GUI (toggle off in prefs to review transfers)
- [x] `meson.build` version synced to 1.5
- [x] Flatpak: `xdg-documents` for drag-and-drop from Documents
- [x] Removed placeholder translate URL from metainfo

---

## Your tasks

- [ ] **App icon** — replace `data/org.gator.Gator.svg` with HIG-compliant design
- [ ] **Screenshots** — add under `data/screenshots/`, update `metainfo.xml` URLs

---

## Optional / later

- [ ] Transfer history log (deferred for v1.x)
- [ ] Flathub submission (GitHub Pages install works without it)
- [ ] `.po` translation files (gettext scaffolding exists; English only today)
- [ ] Single-instance / D-Bus (prevent duplicate windows)

---

## Distribution

| Channel | How users get updates |
|---------|----------------------|
| **Flatpak (Pages)** | Push to `master` → Publish Flatpak workflow |
| **GitHub Release** | Optional changelog only; not required for Flatpak |
| **pip / source** | Needs `croc` on PATH |

Install:
```bash
flatpak install --user --from \
  https://raw.githubusercontent.com/isyourbrainfoss/gator/master/org.gator.Gator.flatpakref
```

Debug: `GATOR_LOG=1 flatpak run org.gator.Gator`
# Gator – Task list

## Status: v1.6.0

Core app, Flatpak, and CI are in place. **v1.6** focuses on honest transfer results, croc 11.3.2, and UX/stability from a multi-agent review.

---

## Done

### Core (P0–P3)
- Modular GTK4/libadwaita app (`app`, `window`, pages, `transfer`, `settings`, `preferences`)
- `Gio.Subprocess` transfers with `\r`/`\n` progress parsing
- GSettings + JSON fallback; empty croc defaults + legacy relay migration
- Flatpak bundles croc **v11.3.2**; GitHub Pages repo (x86_64 + aarch64)
- Meson, desktop, metainfo, CI (black/ruff/mypy/pytest)
- Unit tests: settings, transfer, qr, theme

### UX (v1.5)
- Send: full-width progress, sent checkmarks, completion feedback
- Receive: same completion pattern (status icon, folder row success state)
- Transfer phase labels (Hashing / Sending / Receiving)
- `GATOR_LOG=1` for debug logging

### Polish (v1.5.1 — in repo)
- [x] Receive `--yes` preference existed (v1.6 always passes `--yes` in the GUI; there is no TTY prompt)
- [x] `meson.build` version synced
- [x] Flatpak: `xdg-documents` for drag-and-drop from Documents
- [x] Removed placeholder translate URL from metainfo

### v1.6.0 — reliability and review follow-ups
- [x] Honest transfer outcomes (`get_exit_status` / `get_successful`; fail vs success vs cancel)
- [x] Classify croc errors (invalid code, peer drop, relay, refused, permission) into banners
- [x] Custom send codes via `CROC_SECRET` (not `--code`) so they work on UNIX
- [x] Bundled croc 11.0.1 → **11.3.2** (auto DERP / public relay pool; mixed-version fallback)
- [x] Redact `--pass` / `--text` from the shell log; `--` before file operands
- [x] Isolate croc temp files in a per-send temp cwd; gitignore `croc-stdin-*`
- [x] Confirm quit/close while a transfer is running; inhibit logout/suspend
- [x] Freeze add/remove/drop during send; freeze folder change during receive
- [x] GUI always passes `--yes` (no hung TTY prompts); `--rename` preference
- [x] Empty send state, waiting-for-receiver phase, hide empty QR card
- [x] Receive boxed-list form, paste/scan suffixes, Enter to start, code error state
- [x] Keyboard shortcuts, desktop notifications when unfocused, a11y `update_property`
- [x] Preferences: editable rows, reset confirmation, hash `highway`/`xxhash`
- [x] Version strings synced to 1.6.0

---

## Your tasks

- [ ] **Screenshots** — add under `data/screenshots/`, update `metainfo.xml` URLs if needed

---

## Optional / later

- [ ] Transfer history log (deferred for v1.x)
- [ ] Flathub submission (GitHub Pages install works without it; vendor Go modules for offline builds)
- [ ] `.po` translation files (gettext scaffolding exists; English only today)
- [ ] Webcam / screenshot QR scan (file-image scan is implemented)
- [ ] In-app Accept/Reject if TTY-style prompts are ever required

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

### Definition of done (v1.6)

| Task | Done when |
|------|-----------|
| Honest outcomes | Invalid code / failed croc never shows success checkmarks or “Transfer finished” |
| Custom codes | Prefs custom code ≥ 6 chars starts a send; receiver uses the same phrase |
| croc 11.3.2 | `flatpak run --command=croc org.gator.Gator --version` reports 11.3.2 |
| Secrets | Shell log never contains `--pass` or `--text` values |
| Temp files | `pytest tests/test_transfer.py` leaves no `croc-stdin-*` in the repo root |
| Close confirm | Close/Ctrl+Q during send shows a dialog; dismiss keeps the transfer |
| Tests | `pytest tests/ -q` and `ruff check .` and `black --check .` pass |

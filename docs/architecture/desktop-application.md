# Desktop application boundary

PaperSage has one product UI: `web/src/` is the shared Vite/React application for browsers and Electron. Pages, routes, TanStack Query hooks, schemas and the HTTP API must remain platform-neutral.

Electron is intentionally limited to `web/electron/`:

- `main.cjs` starts the local packaged FastAPI service, owns the frameless window, and exposes only minimize/maximize/close IPC handlers.
- `preload.cjs` exposes that small allowlist as `window.papersageDesktop`; Node integration remains disabled.
- `src/lib/platform.ts` is the sole renderer-side platform boundary. A browser returns no controls, so the custom title bar is not rendered and all regular Web behaviour is unchanged.

`make desktop-dev` runs Vite plus the Electron shell. `make desktop-package-win`, `make desktop-package-mac`, and `make desktop-package-linux` build the shared web bundle, package the Python server with its `web/dist` resources, then produce NSIS, DMG, or AppImage/deb on their native operating system. Never add desktop-only business logic to pages or React components; add narrowly scoped capabilities to the preload bridge and platform module instead.

In Electron, the app shell owns the viewport: the document itself never scrolls, while the central content region provides the single application scroller. Native overflow inside sheets and code blocks uses the same thin themed scrollbar; persistent navigation panes continue to use Radix `ScrollArea`.

Packaged desktop clients use `electron-updater` with the public GitHub Release provider. The updater reads Builder-generated `latest.yml` metadata, prompts before downloading, and asks before restart/install. NSIS on Windows and AppImage on Linux are supported; DEB is intentionally updated by the operating system package manager. macOS auto-update additionally requires a signed release; release CI emits both DMG and ZIP because the ZIP is required for macOS update metadata.

The desktop backend deliberately excludes local RapidOCR/OpenCV. Text PDFs continue to parse locally with PyMuPDF; scanned PDFs use the user's configured vision-capable model. This keeps the OCR feature while avoiding a large native OCR runtime in every installation.

GitHub Actions uses the same native package commands for tagged releases. It builds Windows, macOS, and Linux artifacts on their respective runners, then attaches the generated packages and update metadata to the GitHub Release.

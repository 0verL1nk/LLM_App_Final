# Desktop application boundary

PaperSage has one product UI: `web/src/` is the shared Vite/React application for browsers and Electron. Pages, routes, TanStack Query hooks, schemas and the HTTP API must remain platform-neutral. The desktop shell adds a system tray: closing its window keeps the local service available, while the tray menu's explicit quit action closes the application.

Electron is intentionally limited to `web/electron/`:

- `main.cjs` starts the local packaged FastAPI service, owns the frameless window, and exposes only minimize/maximize/close IPC handlers.
- `preload.cjs` exposes that small allowlist as `window.papersageDesktop`; Node integration remains disabled.
- `src/lib/platform.ts` is the sole renderer-side platform boundary. A browser returns no controls, so the custom title bar is not rendered and all regular Web behaviour is unchanged.

The shared sidebar footer has an account/connection menu. It reports the actual local
mode used by the packaged FastAPI service. Cloud mode is intentionally disabled until
Electron owns authenticated remote endpoint selection and a compatibility check; the
renderer must not turn the development `X-User-Id: local-user` header into a cloud
identity or pretend that an unconfigured endpoint is connected.

`make desktop-dev` runs Vite plus the Electron shell. `make desktop-package-win`, `make desktop-package-mac`, and `make desktop-package-linux` build the shared web bundle, package the Python server with its `web/dist` resources, then produce NSIS, DMG, or AppImage/deb on their native operating system. Never add desktop-only business logic to pages or React components; add narrowly scoped capabilities to the preload bridge and platform module instead.

In Electron, the app shell owns the viewport: the document itself never scrolls, while the central content region provides the single application scroller. Native overflow inside sheets and code blocks uses the same thin themed scrollbar; persistent navigation panes continue to use Radix `ScrollArea`.

Packaged desktop clients use `electron-updater` with the public GitHub Release provider. The updater reads Builder-generated `latest.yml` metadata, prompts before downloading, reports byte and percentage progress globally and in Settings, and asks before restart/install. NSIS on Windows and AppImage on Linux are supported; DEB is intentionally updated by the operating system package manager. Development or portable runs explicitly say that no release update channel is configured - they must never be mislabeled as a software-store installation. macOS auto-update additionally requires a signed release; release CI emits both DMG and ZIP because the ZIP is required for macOS update metadata.

The desktop backend uses local PaddleOCR for document ingestion. PDF pages are rendered with PyMuPDF, images are preserved as pages, and TXT is typeset into pages. Word, Excel, and PowerPoint files are first converted to PDF with an installed Microsoft Office desktop application; LibreOffice is the portable fallback. Models are downloaded on first use into `AGENT_OCR_CACHE_DIR` (or the app cache) rather than embedded in every installer. The runtime selects PP-OCRv6 tiny, small, or medium from the available ONNX Runtime provider, RAM, and CPU capacity; every OCR span retains its page, polygon, and confidence for evidence localization.

OCR output is indexed as normal text while the LanceDB chunk metadata preserves all overlapping OCR locations. A chunk may therefore cite more than one page, which is required for cross-page paragraphs and tables. When the installed Paddle runtime itself has CUDA support, multi-page files are additionally reconstructed through PaddleOCR-VL's `restructure_pages` API, with semantic table merging and title re-leveling. Its generated Markdown is indexed only with layout blocks that can be mapped back to that text, so evidence locations never point at text that was not returned. ONNX CUDA accelerates PP-OCR but does not by itself enable the VL path. Do not implement cross-page joining with text heuristics.

Desktop diagnostics are written as rotating files. PaperSage first uses `<installation directory>/logs` and falls back to Electron's application log directory if the installation location is not writable; the Settings page opens that folder. `main.log`, `backend.log`, `backend-process.log`, and `renderer.log` separate desktop, API, child-process, and renderer failures without exposing them in the normal product UI.

GitHub Actions uses the same native package commands for tagged releases. It builds Windows, macOS, and Linux artifacts on their respective runners, verifies that every generated `latest*.yml` references an attached artifact, then publishes the packages and metadata to the GitHub Release. Windows NSIS artifact names are explicitly configured so the installer and `latest.yml` cannot diverge.

The packaged backend runs Alembic schema migrations at startup. `alembic.ini` and the `alembic/` revision tree are bundled through PyInstaller `--add-data` into `_internal/`, and `web/scripts/package-backend.cjs` fails the build when either asset is missing; `run_migrations()` resolves `script_location` absolutely so migration upgrades never depend on the userData working directory. See `orm-persistence.md` for the persistence layer and raw-SQL audit.

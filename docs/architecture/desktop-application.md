# Desktop application boundary

PaperSage has one product UI: `web/src/` is the shared Vite/React application for browsers and Electron. Pages, routes, TanStack Query hooks, schemas and the HTTP API must remain platform-neutral.

Electron is intentionally limited to `web/electron/`:

- `main.cjs` starts the local packaged FastAPI service, owns the frameless window, and exposes only minimize/maximize/close IPC handlers.
- `preload.cjs` exposes that small allowlist as `window.papersageDesktop`; Node integration remains disabled.
- `src/lib/platform.ts` is the sole renderer-side platform boundary. A browser returns no controls, so the custom title bar is not rendered and all regular Web behaviour is unchanged.

`make desktop-dev` runs Vite plus the Electron shell. `make desktop-package-win`, `make desktop-package-mac`, and `make desktop-package-linux` build the shared web bundle, package the Python server with its `web/dist` resources, then produce NSIS, DMG, or AppImage/deb on their native operating system. Never add desktop-only business logic to pages or React components; add narrowly scoped capabilities to the preload bridge and platform module instead.

In Electron, the app shell owns the viewport: the document itself never scrolls, while the central content region provides the single application scroller. Native overflow inside sheets and code blocks uses the same thin themed scrollbar; persistent navigation panes continue to use Radix `ScrollArea`.

GitHub Actions uses the same native package commands for tagged releases. It builds Windows, macOS, and Linux artifacts on their respective runners, then attaches the generated packages and update metadata to the GitHub Release.

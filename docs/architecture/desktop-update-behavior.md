# Desktop update behavior

Packaged Windows, signed macOS, and AppImage clients check for a new version
after startup. When one is available, PaperSage downloads it in the background
and continues to display normal UI. After download, the updater verifies the
asset and installs it when the application next exits normally. This avoids
starting an NSIS installer while the tray-resident application is still using
its own files.

An update cannot replace a running desktop executable. Per-machine Windows
installations may still require a UAC prompt when the user exits.

The update provider is this repository's GitHub Releases (`provider:
"github"` in `web/package.json`). The Desktop Release workflow attaches all
updater artifacts — `latest*.yml` metadata, platform update packages, and
blockmaps — to the GitHub release alongside the installers, so no external
bucket or CDN is involved. Updates are full downloads; GitHub-hosted feeds do
not serve differential range requests.

Clients on networks where GitHub is unreachable can set the
`PAPERSAGE_UPDATE_FEED` environment variable to a mirror feed URL; the
updater tries the configured mirror once after the primary check fails.

History: releases up to and including 1.13.0 also published updater assets
to a personal Cloudflare R2 bucket (`overlink-papersage-desktop-updates-prod`,
`https://papersage-updates.overlink.top`) and used it as the primary feed.
That path was removed on 2026-08-30; installs still configured against it
will see no further updates from that bucket and should reinstall from
GitHub Releases or set `PAPERSAGE_UPDATE_FEED`.

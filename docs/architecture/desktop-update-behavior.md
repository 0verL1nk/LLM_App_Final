# Desktop update behavior

Packaged Windows, signed macOS, and AppImage clients check for a new version
after startup. When one is available, PaperSage downloads it in the background
and continues to display normal UI. After download, the updater verifies the
asset and installs it when the application next exits normally. This avoids
starting an NSIS installer while the tray-resident application is still using
its own files.

An update cannot replace a running desktop executable. Per-machine Windows
installations may still require a UAC prompt when the user exits.

The update provider is `https://papersage-updates.overlink.top`, backed by the
dedicated R2 bucket `overlink-papersage-desktop-updates-prod`. The Desktop
Release workflow uploads only updater metadata, platform update packages, and
their blockmaps to that bucket. Metadata is `no-store`; versioned packages are
immutable and use multiple HTTP range requests for differential updates.

The release workflow uses R2's S3-compatible multipart API because desktop
installers exceed Wrangler's 300 MiB single-upload limit. It requires the
repository secrets `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`, created with
object read/write access limited to that update bucket.

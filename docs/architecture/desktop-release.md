# Desktop release operations

Desktop packages are produced only on their native operating systems:

| Target | Command | GitHub artifact |
| --- | --- | --- |
| Windows | `make desktop-package-win` | NSIS `.exe` |
| macOS | `make desktop-package-mac` | `.dmg` |
| Linux | `make desktop-package-linux` | `.AppImage` and `.deb` |

All packages use `web/build/icon.svg` as their source icon. Electron Builder converts it to the required native formats at build time; do not maintain separate hand-drawn copies.

The `Desktop Release` workflow validates that a `vX.Y.Z` tag matches both `pyproject.toml` and `web/package.json`, packages the FastAPI service natively on each runner, builds the Python wheel and sdist, then attaches all assets to the GitHub Release. It is the only workflow allowed to create a GitHub Release, and it runs only after every native package job succeeds. Release tags must point to a reviewed commit.

`Prepare Release` creates or updates a release PR from Conventional Commits. `feat:` selects a minor release, `fix:` selects a patch release, and `!` or a `BREAKING CHANGE:` footer selects a major release. The PR synchronizes the Python and web versions. `Release Train` runs at 09:00 Asia/Shanghai on weekdays and merges only a clean `autorelease: pending` version PR. It dispatches `Publish Merged Version`, which verifies the versions, creates the exact `vX.Y.Z` tag, and dispatches the canonical Desktop Release and PyPI workflows. No human tag step is required.

The canonical release workflow also builds the Vite application before producing the Python wheel and sdist. As a result, `pip install paper-sage` followed by `paper-sage` serves the same production web bundle at `http://127.0.0.1:8000`; it does not launch Vite. Electron packages reuse that bundle and add the desktop shell, updater, and native installation behavior.

Unsigned builds remain useful for internal testing but will trigger platform trust warnings. Every public GitHub Release additionally receives a free GitHub OIDC/Sigstore provenance attestation and a `SHA256SUMS.txt` manifest. Consumers can verify a downloaded installer with:

```bash
gh attestation verify PaperSage-Setup.exe -R 0verL1nk/PaperSage
```

This proves the asset was built by the repository's release workflow; it does not replace operating-system publisher trust. For production, configure repository secrets before tagging:

- Windows: `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD`
- macOS signing: `MAC_CSC_LINK`, `MAC_CSC_KEY_PASSWORD`
- macOS notarization: `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`

Certificates and passwords are injected only by GitHub Actions and must never be committed. If signing secrets are absent, the workflow still builds unsigned testable artifacts; do not call those public production releases.

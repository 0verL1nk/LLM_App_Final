# Desktop OCR backend packaging

The Electron backend is packaged with PyInstaller. PaddleX checks optional OCR
dependencies through Python distribution metadata, so omitting their
`.dist-info` directories makes an installed runtime incorrectly report that
`paddlex[ocr]` is missing.

`scripts/paddlex_ocr_pyinstaller_metadata.py` derives the installed base and
OCR-extra distributions from PaddleX metadata. `web/scripts/package-backend.cjs`
passes each one to PyInstaller using `--copy-metadata`, together with PaddleX
data and Paddle binary collection. This follows PaddleOCR's packaging guidance
without collecting every optional PaddleX pipeline and its dependencies.

"""Regression coverage for desktop PaddleX OCR packaging metadata."""

from scripts.paddlex_ocr_pyinstaller_metadata import required_ocr_distributions


def test_required_ocr_distributions_include_runtime_and_ocr_extra() -> None:
    distributions = required_ocr_distributions()

    assert "paddleocr" in distributions
    assert "paddlex" in distributions
    assert "pypdfium2" in distributions

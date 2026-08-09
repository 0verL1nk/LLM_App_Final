"""List the distribution metadata required by PaddleX's OCR extra at runtime."""

from __future__ import annotations

from importlib import metadata

from packaging.requirements import Requirement


def required_ocr_distributions() -> list[str]:
    """Return installed PaddleX OCR dependencies whose metadata must be bundled."""
    installed = {distribution.metadata["Name"].lower() for distribution in metadata.distributions()}
    required = {"paddleocr", "paddlex"}
    for requirement_spec in metadata.requires("paddlex") or []:
        requirement = Requirement(requirement_spec)
        if requirement.marker is None or requirement.marker.evaluate({"extra": "ocr"}):
            if requirement.name.lower() in installed:
                required.add(requirement.name)
    return sorted(required)


if __name__ == "__main__":
    print("\n".join(required_ocr_distributions()))

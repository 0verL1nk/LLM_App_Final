"""Versioned prompt contract for inline, catalog-backed UI fragments."""

from __future__ import annotations

from collections.abc import Iterable

from .a2ui_catalog import A2UICatalogDefinition, registered_a2ui_catalogs


class A2UIOutputContractBuilder:
    """Build the model-facing grammar from server-registered catalogs only."""

    def __init__(self, catalogs: Iterable[A2UICatalogDefinition]) -> None:
        self._catalogs = tuple(catalogs)

    def build(self) -> str:
        """Return an output contract, or no UI instructions when none are registered."""
        if not self._catalogs:
            return ""
        catalog_lines = "\n".join(
            f'- `<ui type="{catalog.fragment_type}">`: {catalog.xml_schema}; use only when {catalog.use_when}.'
            for catalog in self._catalogs
        )
        return f"""[Inline UI output contract]
Keep the response as natural Markdown. Only when an inline visual materially improves
understanding, insert a private XML fragment on its own line. Do not call a UI tool.
Do not output HTML, CSS, JavaScript, SVG, JSON, or A2UI protocol envelopes.

Supported fragment schemas:
{catalog_lines}

For example:
<ui type="research-map">
  <map title="concise title">
    <node label="root concept">
      <evidence ref="a real chunk_id returned this turn" />
      <node label="child concept" />
    </node>
  </map>
</ui>

Use it for a genuine hierarchy, not as decoration. Omit it when prose is clearer.
Use only evidence refs returned by document tools in this turn. The server renders XML
privately through its registered catalog; the XML fragment itself is never visible to the user."""


def build_a2ui_output_contract() -> str:
    """Build the active output contract for every leader system prompt."""
    return A2UIOutputContractBuilder(registered_a2ui_catalogs()).build()


__all__ = ["A2UIOutputContractBuilder", "build_a2ui_output_contract"]

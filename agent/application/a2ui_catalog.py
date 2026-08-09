"""Registered, server-owned descriptions of inline research presentations."""

from __future__ import annotations

from dataclasses import dataclass

from .a2ui_mindmap import CATALOG_ID, MAX_CHILDREN, MAX_DEPTH, MAX_LABEL_LENGTH


@dataclass(frozen=True)
class A2UICatalogDefinition:
    """One output grammar backed by one restricted renderer catalog."""

    fragment_type: str
    catalog_id: str
    xml_schema: str
    use_when: str


def registered_a2ui_catalogs() -> tuple[A2UICatalogDefinition, ...]:
    """Return the catalog manifest available to the active research runtime."""
    return (
        A2UICatalogDefinition(
            fragment_type="research-map",
            catalog_id=CATALOG_ID,
            xml_schema=(
                '<map title="concise title"><node label="root concept">'
                '<evidence ref="a real chunk_id returned this turn" />'
                '<node label="child concept" /></node></map>; '
                f"at most {MAX_DEPTH} levels, {MAX_CHILDREN} children per node, "
                f"and {MAX_LABEL_LENGTH} characters per label"
            ),
            use_when="a genuine evidence-grounded hierarchy is clearer than prose",
        ),
    )


__all__ = ["A2UICatalogDefinition", "registered_a2ui_catalogs"]

"""Baseline revision for the existing PaperSage runtime SQLite schema."""

from __future__ import annotations

revision = "20260809_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Record the pre-existing schema baseline without destructive DDL."""
    return None


def downgrade() -> None:
    """The baseline intentionally owns no schema objects to remove."""
    return None

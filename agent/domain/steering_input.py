"""Contracts for user messages queued into an active Agent Run."""

from enum import StrEnum


class SteeringInputStatus(StrEnum):
    QUEUED = "queued"
    DELIVERING = "delivering"
    DELIVERED = "delivered"


__all__ = ["SteeringInputStatus"]

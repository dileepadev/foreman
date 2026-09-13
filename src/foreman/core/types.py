"""Shared type aliases used across more than one package."""

from __future__ import annotations

from typing import NewType

__all__ = ["RunId", "SpanId", "TenantId"]

RunId = NewType("RunId", str)
SpanId = NewType("SpanId", str)
TenantId = NewType("TenantId", str)

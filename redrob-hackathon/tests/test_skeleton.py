"""Smoke tests for the project skeleton."""

from __future__ import annotations

from src.utils.helpers import batched


def test_batched_yields_expected_chunks() -> None:
    """Verify the shared batching helper preserves order and chunk size."""
    assert list(batched([1, 2, 3], batch_size=2)) == [[1, 2], [3]]


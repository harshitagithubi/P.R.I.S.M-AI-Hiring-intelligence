"""Shared helper functions for scalable data workflows."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TypeVar


T = TypeVar("T")


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists and return its path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def batched(items: Iterable[T], batch_size: int) -> Iterator[list[T]]:
    """Yield items in fixed-size batches."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


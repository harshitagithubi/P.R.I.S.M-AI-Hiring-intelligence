"""Project-wide constants."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
EMBEDDINGS_DIR = PROJECT_ROOT / "models" / "embeddings"

DEFAULT_BATCH_SIZE = 1_000
MAX_CANDIDATE_PROFILES = 100_000


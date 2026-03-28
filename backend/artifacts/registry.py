"""Artifact registry — loads and indexes artifact fixture files."""

from __future__ import annotations

import json
from pathlib import Path

from backend.domain.models import ArtifactSpec


_DEFAULT_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ArtifactRegistry:
    """Loads artifact specs from JSON fixtures and provides lookup."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._fixtures_dir = fixtures_dir or _DEFAULT_FIXTURES_DIR
        self._artifacts: dict[str, ArtifactSpec] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all JSON fixtures from the fixtures directory."""
        self._artifacts.clear()
        if not self._fixtures_dir.exists():
            self._loaded = True
            return

        for path in sorted(self._fixtures_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            spec = ArtifactSpec(**data)
            self._artifacts[spec.artifact_id] = spec

        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get(self, artifact_id: str) -> ArtifactSpec | None:
        self._ensure_loaded()
        return self._artifacts.get(artifact_id)

    def list_all(self) -> list[ArtifactSpec]:
        self._ensure_loaded()
        return list(self._artifacts.values())

    def search(self, query: str) -> ArtifactSpec | None:
        """Find the best matching artifact by checking tags, title, description.

        Simple keyword overlap scoring. Returns None if no match.
        """
        self._ensure_loaded()
        if not self._artifacts:
            return None

        query_words = set(query.lower().split())
        best: ArtifactSpec | None = None
        best_score = 0

        for spec in self._artifacts.values():
            searchable = " ".join([
                spec.title.lower(),
                spec.description.lower(),
                spec.family.lower(),
                " ".join(t.lower() for t in spec.tags),
            ])
            searchable_words = set(searchable.split())
            score = len(query_words & searchable_words)
            if score > best_score:
                best_score = score
                best = spec

        return best if best_score > 0 else None


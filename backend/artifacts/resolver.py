"""Artifact resolver — maps orchestrator decisions to canvas op batches."""

from __future__ import annotations

import copy
import uuid

from backend.artifacts.registry import ArtifactRegistry
from backend.domain.models import (
    ArtifactSpec,
    BackendEvent,
    CanvasOpBatch,
    OrchestratorDecision,
)
from backend.streaming.publisher import EventPublisher


class ArtifactResolver:
    """Resolves an OrchestratorDecision into a CanvasOpBatch.

    1. Searches the registry for a matching artifact
    2. Instantiates the artifact template with parameter injection
    3. Emits events and returns the op batch
    """

    def __init__(self, registry: ArtifactRegistry, publisher: EventPublisher) -> None:
        self._registry = registry
        self._publisher = publisher

    async def resolve(
        self,
        decision: OrchestratorDecision,
        session_id: str,
        drawn_artifacts: list[dict] | None = None,
    ) -> CanvasOpBatch | None:
        """Attempt to resolve a decision into canvas ops.

        Returns None if no matching artifact is found or if the artifact
        (or its family) is already on canvas.
        """
        if decision.intent != "draw_artifact" or not decision.artifact_query:
            return None

        spec = self._registry.search(decision.artifact_query)

        # Deduplication guard: skip if same family already drawn
        if spec and drawn_artifacts:
            drawn_families = {a.get("family") for a in drawn_artifacts}
            if spec.family in drawn_families:
                await self._publisher.publish(BackendEvent(
                    session_id=session_id,
                    kind="warning",
                    payload={
                        "message": (
                            f"Skipped duplicate draw: {spec.artifact_id} "
                            f"(family={spec.family} already on canvas)"
                        ),
                    },
                ))
                return None
        if spec is None:
            await self._publisher.publish(BackendEvent(
                session_id=session_id,
                kind="warning",
                payload={
                    "message": f"No artifact found for query: {decision.artifact_query}",
                },
            ))
            return None

        await self._publisher.publish(BackendEvent(
            session_id=session_id,
            kind="artifact_selected",
            payload={
                "artifact_id": spec.artifact_id,
                "family": spec.family,
                "query": decision.artifact_query,
            },
        ))

        # Instantiate template
        ops = self._instantiate(spec, {})

        batch = CanvasOpBatch(
            session_id=session_id,
            ops=ops,
            artifact_id=spec.artifact_id,
            source="artifact_engine",
        )

        await self._publisher.publish(BackendEvent(
            session_id=session_id,
            kind="artifact_instantiated",
            payload={
                "batch_id": batch.batch_id,
                "artifact_id": spec.artifact_id,
                "op_count": len(ops),
            },
        ))

        return batch

    def _instantiate(
        self,
        spec: ArtifactSpec,
        params: dict,
    ) -> list[dict]:
        """Deep-copy the shape template and inject parameters + unique IDs."""
        ops: list[dict] = []

        for shape in spec.shape_template:
            shape_copy = copy.deepcopy(shape)

            # Assign a unique instance ID
            shape_copy["id"] = f"shape:{uuid.uuid4().hex[:8]}"

            # Inject parameters into props if present
            if "props" in shape_copy and params:
                for key, value in params.items():
                    if key in shape_copy["props"]:
                        shape_copy["props"][key] = value

            ops.append({
                "op_type": "create_shape",
                "shape": shape_copy,
            })

        return ops


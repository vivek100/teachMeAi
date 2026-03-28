"""Annotation handler — generates canvas ops to annotate existing artifacts."""

from __future__ import annotations

import uuid

from backend.domain.models import (
    BackendEvent,
    CanvasOpBatch,
    OrchestratorDecision,
)
from backend.domain.state import SessionState
from backend.streaming.publisher import EventPublisher


class Annotator:
    """Generates annotation ops (labels, callouts) for existing canvas artifacts.

    When the orchestrator decides to annotate, this handler finds the most
    recent artifact matching the topic and adds a text callout below it.
    """

    def __init__(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    async def annotate(
        self,
        decision: OrchestratorDecision,
        state: SessionState,
    ) -> CanvasOpBatch | None:
        """Generate annotation ops for the current topic.

        Returns a CanvasOpBatch with annotation shapes, or None if there's
        nothing to annotate.
        """
        if decision.intent != "annotate":
            return None

        # Find the most recent drawn artifact matching this topic
        target = self._find_target_artifact(decision.topic, state)
        if not target:
            return None

        annotation_text = decision.annotation_text or decision.rationale
        if not annotation_text:
            return None

        # Generate annotation ops — a callout text placed relative to the artifact
        ops = self._build_annotation_ops(target, annotation_text)

        batch = CanvasOpBatch(
            session_id=state.session_id,
            ops=ops,
            artifact_id=target.get("artifact_id"),
            source="annotation",
        )

        await self._publisher.publish(BackendEvent(
            session_id=state.session_id,
            kind="annotation_added",
            payload={
                "batch_id": batch.batch_id,
                "target_artifact": target.get("artifact_id"),
                "annotation_text": annotation_text[:100],
                "op_count": len(ops),
            },
        ))

        return batch

    def _find_target_artifact(
        self,
        topic: str | None,
        state: SessionState,
    ) -> dict | None:
        """Find the most recent drawn artifact matching the topic."""
        if not state.drawn_artifacts:
            return None

        if not topic:
            # Default to the most recently drawn artifact
            return state.drawn_artifacts[-1]

        topic_lower = topic.lower()
        # Search in reverse (most recent first)
        for artifact in reversed(state.drawn_artifacts):
            artifact_topic = artifact.get("topic", "").lower()
            artifact_family = artifact.get("family", "").lower()
            if (
                topic_lower in artifact_topic
                or artifact_topic in topic_lower
                or topic_lower in artifact_family
                or artifact_family in topic_lower
            ):
                return artifact

        # Fallback: return the most recent artifact
        return state.drawn_artifacts[-1]

    def _build_annotation_ops(
        self,
        target: dict,
        annotation_text: str,
    ) -> list[dict]:
        """Build annotation shapes — a highlighted callout note."""
        # Count existing annotations to offset position
        annotation_id = f"shape:{uuid.uuid4().hex[:8]}"
        connector_id = f"shape:{uuid.uuid4().hex[:8]}"

        ops = [
            {
                "op_type": "create_shape",
                "shape": {
                    "type": "geo",
                    "x": 820,
                    "y": 20,
                    "props": {
                        "geo": "rectangle",
                        "w": 300,
                        "h": 80,
                        "text": annotation_text[:120],
                        "color": "yellow",
                        "fill": "semi",
                        "font": "sans",
                        "size": "s",
                    },
                    "id": annotation_id,
                },
            },
            {
                "op_type": "create_shape",
                "shape": {
                    "type": "arrow",
                    "x": 800,
                    "y": 60,
                    "props": {
                        "start": {"x": 20, "y": 0},
                        "end": {"x": -20, "y": 0},
                        "color": "yellow",
                        "dash": "dashed",
                    },
                    "id": connector_id,
                },
            },
        ]

        return ops


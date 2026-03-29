"""Orchestration service — connects the orchestrator agent to the pipeline."""

from __future__ import annotations

import railtracks as rt

from backend.artifacts.annotator import Annotator
from backend.artifacts.registry import ArtifactRegistry
from backend.artifacts.resolver import ArtifactResolver
from backend.domain.models import (
    BackendEvent,
    CanvasOpBatch,
    OrchestratorDecision,
    TranscriptWindow,
)
from backend.domain.state import SessionState
from backend.logging_utils import get_logger
from backend.orchestration.prompts import (
    FAMILY_HIERARCHY,
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator_user_prompt,
)
from backend.orchestration.tools import create_tools
from backend.streaming.publisher import EventPublisher

logger = get_logger("orchestration.service")

class OrchestrationService:
    """Runs the orchestrator agent on a transcript window and resolves artifacts."""

    def __init__(
        self,
        registry: ArtifactRegistry,
        resolver: ArtifactResolver,
        publisher: EventPublisher,
        llm=None,
    ) -> None:
        self._registry = registry
        self._resolver = resolver
        self._annotator = Annotator(publisher)
        self._publisher = publisher
        self._llm = llm

    def _build_system_prompt(self, state: SessionState) -> str:
        families = [s.family for s in self._registry.list_all()]
        unique_families = sorted(set(families))

        # Build recent decisions with artifact context
        recent = ""
        if state.recent_decisions:
            lines = []
            for d in state.recent_decisions[-5:]:
                if d.intent == "draw_artifact" and d.artifact_query:
                    lines.append(
                        f"  - {d.intent}: query=\"{d.artifact_query}\", topic={d.topic}, confidence={d.confidence}"
                    )
                else:
                    lines.append(f"  - {d.intent}: topic={d.topic}, confidence={d.confidence}")
            recent = "\n".join(lines)
        else:
            recent = "  (none yet)"

        # Build canvas state from drawn artifacts
        canvas = ""
        if state.drawn_artifacts:
            lines = []
            for a in state.drawn_artifacts:
                lines.append(
                    f"  - {a['artifact_id']} (family={a['family']}, topic={a.get('topic', 'unknown')})"
                )
            canvas = "\n".join(lines)
        else:
            canvas = "  (empty — nothing drawn yet)"

        # Build concept hierarchy summary
        hierarchy_lines = []
        for parent, children in FAMILY_HIERARCHY.items():
            hierarchy_lines.append(f"  - {parent} → {', '.join(children)}")
        hierarchy = "\n".join(hierarchy_lines) if hierarchy_lines else "  (none defined)"

        return ORCHESTRATOR_SYSTEM_PROMPT.format(
            artifact_families=", ".join(unique_families) if unique_families else "(none loaded)",
            recent_decisions=recent,
            canvas_state=canvas,
            concept_hierarchy=hierarchy,
        )

    async def process_window(
        self,
        state: SessionState,
        window: TranscriptWindow,
    ) -> CanvasOpBatch | None:
        """Run orchestration on a transcript window.

        Returns a CanvasOpBatch if the agent decides to draw, else None.
        """
        if self._llm is None:
            raise RuntimeError("No LLM configured for OrchestrationService")

        tools = create_tools(self._registry, state)
        system_prompt = self._build_system_prompt(state)

        agent = rt.agent_node(
            name="Lecture Orchestrator",
            llm=self._llm,
            system_message=system_prompt,
            tool_nodes=tools,
            output_schema=OrchestratorDecision,
        )

        user_prompt = build_orchestrator_user_prompt(
            combined_text=window.combined_text,
            active_topic=state.active_topic,
            canvas_artifact_count=len(state.drawn_artifacts),
        )

        result = await rt.call(agent, user_prompt)
        decision: OrchestratorDecision = result.structured
        logger.info(
            "decision produced | session_id=%s | intent=%s | topic=%s | artifact_query=%s | confidence=%s",
            state.session_id,
            decision.intent,
            decision.topic,
            decision.artifact_query,
            decision.confidence,
        )

        # Record decision
        state.recent_decisions.append(decision)
        if len(state.recent_decisions) > 20:
            state.recent_decisions = state.recent_decisions[-20:]

        if decision.topic:
            state.active_topic = decision.topic

        await self._publisher.publish(BackendEvent(
            session_id=state.session_id,
            kind="decision_made",
            payload=decision.model_dump(),
        ))

        # Resolve to canvas ops if applicable
        if decision.intent == "draw_artifact":
            batch = await self._resolver.resolve(
                decision, state.session_id, drawn_artifacts=state.drawn_artifacts
            )
            if batch:
                logger.info(
                    "artifact batch ready | session_id=%s | batch_id=%s | artifact_id=%s | op_count=%s",
                    state.session_id,
                    batch.batch_id,
                    batch.artifact_id,
                    len(batch.ops),
                )
                state.pending_batches.append(batch)
                # Track what's on canvas for dedup
                state.drawn_artifacts.append({
                    "artifact_id": batch.artifact_id,
                    "family": self._get_artifact_family(batch.artifact_id),
                    "topic": decision.topic or "unknown",
                })
                await self._publisher.publish(BackendEvent(
                    session_id=state.session_id,
                    kind="op_batch_ready",
                    payload={
                        "batch_id": batch.batch_id,
                        "op_count": len(batch.ops),
                        "artifact_id": batch.artifact_id,
                        "batch": batch.model_dump(mode="json"),
                    },
                ))
            return batch

        # Handle annotate intent
        if decision.intent == "annotate":
            batch = await self._annotator.annotate(decision, state)
            if batch:
                logger.info(
                    "annotation batch ready | session_id=%s | batch_id=%s | op_count=%s",
                    state.session_id,
                    batch.batch_id,
                    len(batch.ops),
                )
                state.pending_batches.append(batch)
                await self._publisher.publish(BackendEvent(
                    session_id=state.session_id,
                    kind="op_batch_ready",
                    payload={
                        "batch_id": batch.batch_id,
                        "op_count": len(batch.ops),
                        "artifact_id": batch.artifact_id,
                        "batch": batch.model_dump(mode="json"),
                    },
                ))
            return batch

        return None

    def _get_artifact_family(self, artifact_id: str) -> str:
        """Look up the family for an artifact_id from the registry."""
        spec = self._registry.get(artifact_id)
        if spec:
            return spec.family
        # Fallback: derive family from artifact_id (e.g. "token_grid_basic" → "token_grid")
        parts = artifact_id.rsplit("_", 1)
        return parts[0] if len(parts) > 1 else artifact_id

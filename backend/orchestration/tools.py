"""Railtracks function_node tools for the orchestrator agent."""

from __future__ import annotations

import railtracks as rt

from backend.artifacts.registry import ArtifactRegistry
from backend.domain.state import SessionState


def create_tools(registry: ArtifactRegistry, state: SessionState):
    """Create Railtracks function_node tools bound to the current session state.

    Returns a list of tool nodes ready to pass to rt.agent_node().
    """

    @rt.function_node
    def get_recent_transcript() -> str:
        """Get the most recent transcript window text.

        Returns the combined text of the latest transcript window,
        or a message indicating no transcript is available yet.
        """
        if state.recent_windows:
            return state.recent_windows[-1].combined_text
        return "No transcript available yet."

    @rt.function_node
    def get_recent_decisions() -> str:
        """Get the orchestrator's recent decisions for context.

        Returns a summary of the last few decisions to avoid repetition.
        """
        if not state.recent_decisions:
            return "No previous decisions."
        lines = []
        for d in state.recent_decisions[-5:]:
            lines.append(f"- {d.intent}: {d.rationale} (topic={d.topic})")
        return "\n".join(lines)

    @rt.function_node
    def find_matching_artifact(query: str) -> str:
        """Search the artifact registry for a visual matching the query.

        Args:
            query (str): A short description of the visual needed (e.g. 'tokenization grid').
        """
        # Gemini sometimes wraps the query in a dict like {'description': '...'}
        if isinstance(query, dict):
            query = query.get("description", "") or query.get("query", "") or str(query)
        spec = registry.search(query)
        if spec is None:
            return "No matching artifact found."
        return (
            f"Found: {spec.artifact_id} (family={spec.family})\n"
            f"Title: {spec.title}\n"
            f"Description: {spec.description}\n"
            f"Tags: {', '.join(spec.tags)}"
        )

    return [get_recent_transcript, get_recent_decisions, find_matching_artifact]


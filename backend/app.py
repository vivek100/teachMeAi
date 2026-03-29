"""FastAPI application factory for TeachWithMeAI backend."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import init_routes, router
from backend.artifacts.registry import ArtifactRegistry
from backend.artifacts.resolver import ArtifactResolver
from backend.domain.state import SessionStore
from backend.logging_utils import configure_logging, get_logger
from backend.orchestration.service import OrchestrationService
from backend.streaming.publisher import EventPublisher
from backend.streaming.subscribers import ConsoleSubscriber, SessionStoreSubscriber
from backend.streaming.ws import SessionStreamHub
from backend.transcript.ingest import ChunkIngestor
from backend.transcript.windowing import WindowBuilder

logger = get_logger("app")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _load_environment()
    configure_logging()

    app = FastAPI(title="TeachWithMeAI", version="0.1.0")
    _configure_cors(app)

    publisher = EventPublisher()
    store = SessionStore()
    stream_hub = SessionStreamHub()

    publisher.subscribe(ConsoleSubscriber())
    publisher.subscribe(SessionStoreSubscriber(store))
    publisher.subscribe(stream_hub)

    ingestor = ChunkIngestor(publisher)
    windower = WindowBuilder(publisher, window_size=6, min_new_chunks=3)

    registry = ArtifactRegistry()
    registry.load()

    resolver = ArtifactResolver(registry, publisher)
    llm = _get_llm()

    orchestration = OrchestrationService(
        registry=registry,
        resolver=resolver,
        publisher=publisher,
        llm=llm,
    )

    deps = {
        "ingestor": ingestor,
        "windower": windower,
        "orchestration": orchestration,
        "registry": registry,
        "publisher": publisher,
        "stream_hub": stream_hub,
    }
    init_routes(store, deps)
    app.include_router(router)

    logger.info(
        "application initialized | registry_count=%s | llm_configured=%s",
        len(registry.list_all()),
        llm is not None,
    )

    return app


def _load_environment() -> None:
    """Load env vars from backend/.env and normalize provider key names."""
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path if env_path.exists() else None)

    for canonical_key, fallback_keys in {
        "GEMINI_API_KEY": ("gemini_api_key",),
        "OPENAI_API_KEY": ("openai_api_key",),
        "ANTHROPIC_API_KEY": ("anthropic_api_key",),
    }.items():
        if os.getenv(canonical_key):
            continue
        for fallback_key in fallback_keys:
            fallback_value = os.getenv(fallback_key)
            if fallback_value:
                os.environ[canonical_key] = fallback_value
                break


def _configure_cors(app: FastAPI) -> None:
    """Allow the local frontend dev server to call the API directly."""
    configured_origins = os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
    )
    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _get_llm():
    """Try to create a Railtracks LLM from environment variables."""
    try:
        import railtracks as rt

        if os.getenv("OPENAI_API_KEY"):
            return rt.llm.OpenAILLM("gpt-5.4-mini")
        if os.getenv("GEMINI_API_KEY"):
            return rt.llm.GeminiLLM("gemini-3-flash-preview")
        if os.getenv("ANTHROPIC_API_KEY"):
            return rt.llm.AnthropicLLM("claude-3-5-sonnet")
    except ImportError:
        pass

    logger.warning("no LLM configured")
    return None


app = create_app()

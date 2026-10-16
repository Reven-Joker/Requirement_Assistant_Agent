"""Search helper for local RAG references."""

from __future__ import annotations

from typing import Any

from app.core.logger import logger
from app.storage.repo_memory import search_memory_sync


def search_references(
    query: str,
    max_results: int = 5,
    memory_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search the local ChromaDB memory for relevant cases and patterns."""
    logger.info(f"Search Tool called: query={query[:80]}")
    return search_memory_sync(
        query=query,
        top_k=max_results,
        memory_types=memory_types,
    )

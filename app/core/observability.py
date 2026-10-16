"""Lightweight task and node observability helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from langgraph.errors import GraphInterrupt

from app.core.logger import logger


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trace_node(node_name: str, llm_calls: int = 1):
    """Wrap a LangGraph node and append runtime metrics to its output."""

    def decorator(func: Callable[[dict], dict]):
        def wrapper(state: dict) -> dict:
            started = time.perf_counter()
            try:
                result = func(state)
            except GraphInterrupt:
                raise
            except Exception:
                duration = time.perf_counter() - started
                _record_error(state, node_name, duration)
                raise

            duration = time.perf_counter() - started
            if not isinstance(result, dict):
                return result

            metadata = dict(state.get("metadata") or {})
            metadata.update(result.get("metadata") or {})
            metrics = dict(metadata.get("metrics") or {})
            node_latencies = list(metrics.get("node_latencies") or [])
            node_latencies.append({"node": node_name, "duration_seconds": round(duration, 4)})
            metrics["node_latencies"] = node_latencies
            metrics["node_latency_seconds"] = round(
                sum(item["duration_seconds"] for item in node_latencies) / len(node_latencies),
                4,
            )
            metrics["llm_call_count"] = int(metrics.get("llm_call_count") or 0) + llm_calls
            metrics.setdefault("node_error_count", 0)
            metadata["metrics"] = metrics

            logs = list(result.get("execution_logs") or [])
            logs.append(
                {
                    "node": node_name,
                    "timestamp": utc_now_iso(),
                    "duration_seconds": round(duration, 4),
                    "event": "node_completed",
                }
            )
            result["metadata"] = metadata
            result["execution_logs"] = logs
            return result

        return wrapper

    return decorator


def merge_task_metric(state_snapshot: dict[str, Any] | None, **metrics: Any) -> dict[str, Any]:
    state = dict(state_snapshot or {})
    metadata = dict(state.get("metadata") or {})
    current = dict(metadata.get("metrics") or {})
    current.update({key: value for key, value in metrics.items() if value is not None})
    metadata["metrics"] = current
    state["metadata"] = metadata
    return state


def extract_metrics(state_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    return dict(((state_snapshot or {}).get("metadata") or {}).get("metrics") or {})


def _record_error(state: dict, node_name: str, duration: float) -> None:
    metadata = dict(state.get("metadata") or {})
    metrics = dict(metadata.get("metrics") or {})
    metrics["node_error_count"] = int(metrics.get("node_error_count") or 0) + 1
    metadata["metrics"] = metrics
    logger.error(
        "Node execution failed",
        extra={
            "node": node_name,
            "duration_seconds": round(duration, 4),
            "task_id": state.get("task_id", ""),
        },
    )

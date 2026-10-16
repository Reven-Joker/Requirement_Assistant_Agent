"""In-process asyncio task queue for non-blocking Agent workflow execution."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

from app.core.logger import logger
from app.core.observability import merge_task_metric, utc_now_iso
from app.graph.builder import get_graph
from app.graph.checkpoints import has_checkpoint
from app.storage import repo_task


@dataclass
class WorkflowJob:
    task_id: str
    payload: dict[str, Any] | Command
    kind: str = "start"
    enqueued_at: float = field(default_factory=time.perf_counter)


_queue: asyncio.Queue[WorkflowJob] | None = None
_worker_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None

# per-task 进度队列：task_id -> asyncio.Queue，SSE 端点从这里读取事件
_progress_queues: dict[str, asyncio.Queue] = {}
_PROGRESS_SENTINEL = None  # 放入 queue 表示流结束


def get_or_create_progress_queue(task_id: str) -> asyncio.Queue:
    """获取或创建 task 的进度队列，SSE 端点调用。"""
    if task_id not in _progress_queues:
        _progress_queues[task_id] = asyncio.Queue(maxsize=256)
    return _progress_queues[task_id]


def _drop_progress_queue(task_id: str) -> None:
    _progress_queues.pop(task_id, None)


async def start_worker(*, recover: bool = True) -> None:
    """Start the background worker once per process."""
    global _queue, _worker_task, _stop_event
    if _queue is None:
        _queue = asyncio.Queue()
    if _stop_event is None:
        _stop_event = asyncio.Event()
    if _worker_task is None or _worker_task.done():
        _stop_event.clear()
        _worker_task = asyncio.create_task(_worker_loop(), name="agent-task-worker")
    if recover:
        await recover_pending_tasks()


async def stop_worker() -> None:
    """Stop the background worker gracefully."""
    global _worker_task
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task is not None:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None


async def enqueue_start(task_id: str, initial_state: dict[str, Any]) -> None:
    await _ensure_queue()
    await _queue.put(WorkflowJob(task_id=task_id, payload=initial_state, kind="start"))  # type: ignore[union-attr]


async def enqueue_resume(task_id: str, resume_data: Any) -> None:
    await _ensure_queue()
    await _queue.put(
        WorkflowJob(
            task_id=task_id,
            payload=Command(resume=resume_data),
            kind="resume",
        )
    )  # type: ignore[union-attr]


async def recover_pending_tasks() -> dict[str, int]:
    """Recover DB-persisted tasks that lost their in-process queue entry."""
    await _ensure_queue_started_only()
    recovered = {"queued": 0, "running": 0, "waiting_human": 0, "error": 0}
    tasks = await repo_task.list_tasks_by_status(["queued", "running", "waiting_human"], limit=500)
    for task in tasks:
        task_id = task["task_id"]
        snapshot = task.get("state_snapshot") or {}
        if task["status"] == "queued":
            payload = snapshot or {
                "user_input": task.get("user_input", ""),
                "task_id": task_id,
                "max_reflow_count": 2,
            }
            await _queue.put(WorkflowJob(task_id=task_id, payload=payload, kind="start"))  # type: ignore[union-attr]
            recovered["queued"] += 1
            continue

        if task["status"] == "waiting_human":
            snapshot = merge_task_metric(
                snapshot,
                checkpoint_recovered=has_checkpoint(task_id),
                state_persistence_coverage=1.0 if snapshot else 0.0,
            )
            await repo_task.update_task(task_id, state_snapshot=snapshot)
            recovered["waiting_human"] += 1
            continue

        if has_checkpoint(task_id):
            await repo_task.update_task(task_id, status="queued", current_node="queued")
            payload = snapshot or {
                "user_input": task.get("user_input", ""),
                "task_id": task_id,
                "max_reflow_count": 2,
            }
            await _queue.put(WorkflowJob(task_id=task_id, payload=payload, kind="start"))  # type: ignore[union-attr]
            recovered["running"] += 1
        else:
            snapshot = merge_task_metric(
                snapshot,
                background_task_success=False,
                checkpoint_recovered=False,
            )
            snapshot["error_message"] = "Task was running during restart and no checkpoint was found."
            await repo_task.update_task(
                task_id,
                status="error",
                state_snapshot=snapshot,
                current_node=snapshot.get("current_node", task.get("current_node", "")),
            )
            recovered["error"] += 1
    return recovered


def make_config(task_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": task_id}}


async def _ensure_queue() -> None:
    if _queue is None or _worker_task is None or _worker_task.done():
        await _ensure_queue_started_only()


async def _ensure_queue_started_only() -> None:
    global _queue, _worker_task, _stop_event
    if _queue is None:
        _queue = asyncio.Queue()
    if _stop_event is None:
        _stop_event = asyncio.Event()
    if _worker_task is None or _worker_task.done():
        _stop_event.clear()
        _worker_task = asyncio.create_task(_worker_loop(), name="agent-task-worker")


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        job = await _queue.get()
        try:
            await _run_job(job)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.error(f"Background workflow job failed: {exc}", extra={"task_id": job.task_id})
        finally:
            _queue.task_done()


async def _run_job(job: WorkflowJob) -> None:
    queue_wait_seconds = round(time.perf_counter() - job.enqueued_at, 4)
    task = await repo_task.get_task(job.task_id)
    if task is None:
        logger.warning(f"Skipping missing task {job.task_id}")
        return

    state_snapshot = merge_task_metric(
        task.get("state_snapshot") or {},
        queue_wait_seconds=queue_wait_seconds,
        background_started_at=utc_now_iso(),
    )
    await repo_task.update_task(
        job.task_id,
        status="running",
        state_snapshot=state_snapshot,
    )

    graph = get_graph()
    config = make_config(job.task_id)
    started = time.perf_counter()
    progress_q = _progress_queues.get(job.task_id)

    try:
        # 同步节点必须在线程里跑，避免阻塞事件循环
        # 节点进度通过执行前后的 checkpoint history diff 推断，而非 astream_events
        result = await asyncio.to_thread(graph.invoke, job.payload, config)
    except Exception as exc:
        try:
            values = graph.get_state(config).values
        except Exception:
            values = None
        if isinstance(values, dict) and values:
            state_snapshot = {**state_snapshot, **safe_serialize(values)}
        state_snapshot = merge_task_metric(state_snapshot, background_task_success=False, node_error_count=1)
        state_snapshot["error_message"] = str(exc)
        await repo_task.update_task(
            job.task_id, status="error",
            current_node=state_snapshot.get("current_node", ""),
            state_snapshot=state_snapshot,
        )
        if progress_q is not None:
            await _push(progress_q, {"type": "error", "message": str(exc)})
            await progress_q.put(_PROGRESS_SENTINEL)
            _drop_progress_queue(job.task_id)
        logger.error(f"Workflow execution failed: {exc}", extra={"task_id": job.task_id})
        return

    duration = round(time.perf_counter() - started, 4)
    interrupt_info = extract_interrupt(result)
    status = "waiting_human" if interrupt_info else "completed"
    state_snapshot = safe_serialize(result)
    state_snapshot = merge_task_metric(
        state_snapshot,
        background_task_success=True,
        background_duration_seconds=duration,
        queue_wait_seconds=queue_wait_seconds,
        interrupted_task_recovered=job.kind == "resume",
        resume_success=True if job.kind == "resume" else None,
    )
    if interrupt_info:
        state_snapshot["interrupt_info"] = interrupt_info

    await repo_task.update_task(
        job.task_id,
        status=status,
        current_node=state_snapshot.get("current_node", ""),
        state_snapshot=state_snapshot,
        reflow_count=state_snapshot.get("reflow_count", 0),
    )
    if status == "completed":
        await repo_task.update_task(job.task_id, result=state_snapshot)

    # 推送节点完成事件和最终状态到进度队列
    if progress_q is not None:
        node = state_snapshot.get("current_node", "")
        if node:
            await _push(progress_q, {"type": "node_end", "node": node, "output": {}})
        if interrupt_info:
            await _push(progress_q, {"type": "interrupt", "node": node, "data": interrupt_info})
        await _push(progress_q, {"type": "done", "status": status})
        await progress_q.put(_PROGRESS_SENTINEL)
        _drop_progress_queue(job.task_id)


async def _push(q: asyncio.Queue, event: dict) -> None:
    """非阻塞推送，queue 满时丢弃（SSE 客户端未连接时不阻塞 worker）。"""
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass


def extract_interrupt(result: Any) -> Any | None:
    if isinstance(result, dict) and "__interrupt__" in result:
        return _jsonable(result["__interrupt__"])
    return None


def safe_serialize(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            if key.startswith("__"):
                continue
            clean[key] = _jsonable(value)
        return clean
    return {}


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except (TypeError, ValueError):
        if isinstance(value, tuple):
            return [_jsonable(item) for item in value]
        if isinstance(value, list):
            return [_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        return str(value)

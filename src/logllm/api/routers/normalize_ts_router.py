# src/logllm/api/routers/normalize_ts_router.py
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ...utils.logger import Logger
from ...utils.database import ElasticsearchDatabase
from ...config import config as cfg
from ...agents.timestamp_normalizer import (
    TimestampNormalizerAgent,
    DEFAULT_BATCH_SIZE_NORMALIZER,
)
from ..models.normalize_ts_models import (
    NormalizeTsRunRequest,
    NormalizeTsTaskStatusResponse,
)
from ..models.common_models import MessageResponse


router = APIRouter()
logger = Logger()

NORMALIZE_TS_TASKS: Dict[str, Any] = {}


def update_normalize_ts_task_status(
    task_id: str,
    status: str,
    detail: str = "",
    completed: bool = False,
    error: Optional[str] = None,
    result_summary: Optional[
        Dict[str, Any]
    ] = None,  # Should match TimestampNormalizerOrchestratorState's overall_group_results
):
    if task_id not in NORMALIZE_TS_TASKS:
        NORMALIZE_TS_TASKS[task_id] = {}
    NORMALIZE_TS_TASKS[task_id]["status"] = status
    NORMALIZE_TS_TASKS[task_id]["progress_detail"] = detail
    NORMALIZE_TS_TASKS[task_id]["completed"] = completed
    NORMALIZE_TS_TASKS[task_id]["error"] = error
    NORMALIZE_TS_TASKS[task_id]["last_updated"] = datetime.now().isoformat()
    if result_summary:
        NORMALIZE_TS_TASKS[task_id]["result_summary"] = result_summary
    logger.debug(f"Normalize TS Task {task_id} status updated: {status} - {detail}")


def run_normalize_ts_background_task(task_id: str, request: NormalizeTsRunRequest):
    action_desc = (
        "Normalize Timestamps"
        if request.action == "normalize"
        else "Delete @timestamp Field"
    )
    group_target_desc = (
        f"group '{request.group_name}'"
        if request.group_name and not request.all_groups
        else "ALL groups"
    )

    update_normalize_ts_task_status(
        task_id,
        "Initializing",
        f"Preparing to {action_desc.lower()} for {group_target_desc}",
    )
    logger.info(
        f"Task {task_id}: Background Timestamp Normalizer task started. Action: '{request.action}', Target: {group_target_desc}"
    )

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            err_msg = "Elasticsearch not available."
            logger.error(f"Task {task_id}: {err_msg}")
            update_normalize_ts_task_status(
                task_id, "Error", err_msg, completed=True, error=err_msg
            )
            return

        agent = TimestampNormalizerAgent(db=db)

        target_groups_for_agent: Optional[List[str]] = None
        if request.all_groups:
            target_groups_for_agent = None  # Agent handles fetching all groups
        elif request.group_name:
            target_groups_for_agent = [request.group_name]
        else:  # Should be caught by validation, but defensive
            err_msg = "Invalid group selection for normalize-ts task."
            logger.error(f"Task {task_id}: {err_msg}")
            update_normalize_ts_task_status(
                task_id, "Error", err_msg, completed=True, error=err_msg
            )
            return

        update_normalize_ts_task_status(
            task_id, "Running", f"Processing {group_target_desc}..."
        )

        final_state = agent.run(
            action=request.action,
            target_groups=target_groups_for_agent,
            limit_per_group=request.limit_per_group,
            batch_size=request.batch_size,
        )

        # Store the 'overall_group_results' part of the agent's final_state as the task's result_summary
        task_result_summary = final_state.get("overall_group_results", {})

        success_msg = f"Timestamp Normalizer task ({request.action}) for {group_target_desc} finished."
        logger.info(f"Task {task_id}: {success_msg}")
        update_normalize_ts_task_status(
            task_id,
            "Completed",
            success_msg,
            completed=True,
            result_summary=task_result_summary,
        )

    except Exception as e:
        err_msg = f"Error during Timestamp Normalizer task: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_normalize_ts_task_status(
            task_id, "Error", err_msg, completed=True, error=err_msg
        )


@router.post("/run", response_model=MessageResponse)
async def run_timestamp_normalization(
    request: NormalizeTsRunRequest, background_tasks: BackgroundTasks
):
    if request.action not in ["normalize", "remove_field"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid action specified. Must be 'normalize' or 'remove_field'.",
        )

    if not request.all_groups and not request.group_name:
        raise HTTPException(
            status_code=400,
            detail="Either 'group_name' must be specified or 'all_groups' must be true.",
        )

    if request.all_groups and request.group_name:
        logger.warning(
            "Both all_groups=true and a group_name were provided. Prioritizing all_groups."
        )
        # No need to error, just let all_groups take precedence in the background task logic.

    if request.action == "remove_field" and not request.confirm_delete:
        # In a real scenario, the frontend should handle confirmation.
        # If API is called directly, this check might be useful or removed if FE always sends confirm_delete=true after its own check.
        logger.info(
            "Deletion action requested without explicit confirmation flag (confirm_delete=false). Frontend should manage confirmation."
        )
        # Not raising HTTPException here assuming frontend handles confirmation.

    task_id = str(uuid.uuid4())
    NORMALIZE_TS_TASKS[task_id] = {
        "status": "Pending",
        "progress_detail": "",
        "completed": False,
        "error": None,
        "last_updated": datetime.now().isoformat(),
        "result_summary": None,
    }

    background_tasks.add_task(run_normalize_ts_background_task, task_id, request)

    action_desc = (
        "Timestamp normalization"
        if request.action == "normalize"
        else "Deletion of @timestamp field"
    )
    group_desc = (
        f"group '{request.group_name}'"
        if request.group_name and not request.all_groups
        else "all groups"
    )

    return MessageResponse(
        message=f"{action_desc} process initiated for {group_desc}. Task ID: {task_id}"
    )


@router.get("/task-status/{task_id}", response_model=NormalizeTsTaskStatusResponse)
async def get_normalize_ts_task_status(task_id: str):
    task_info = NORMALIZE_TS_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Normalize TS Task ID not found.")
    return NormalizeTsTaskStatusResponse(task_id=task_id, **task_info)

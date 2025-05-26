# src/logllm/api/routers/static_grok_parse_router.py
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import (  # FileResponse might be removable
    FileResponse,
    JSONResponse,
)
from pydantic import BaseModel, Field

from ...agents.static_grok_parser import StaticGrokParserAgent
from ...agents.static_grok_parser.api.es_data_service import ElasticsearchDataService
from ...config import config as cfg
from ...utils.database import ElasticsearchDatabase
from ...utils.logger import Logger
from ..models.common_models import MessageResponse


class StaticGrokRunRequest(BaseModel):
    group_name: Optional[str] = None
    all_groups: bool = False
    clear_previous_results: bool = False
    grok_patterns_file_path_on_server: str = Field(
        ..., description="Absolute path to a Grok patterns YAML file on the server."
    )


class StaticGrokDeleteRequest(BaseModel):
    group_name: Optional[str] = None
    all_groups: bool = False


class TaskInfo(BaseModel):
    task_id: str
    message: str


class StaticGrokParseStatusItem(BaseModel):
    log_file_id: str
    group_name: Optional[str] = None
    log_file_relative_path: Optional[str] = None
    last_line_number_parsed_by_grok: int
    last_total_lines_by_collector: int
    last_parse_timestamp: Optional[str] = None
    last_parse_status: Optional[str] = None


class StaticGrokStatusListResponse(BaseModel):
    statuses: List[StaticGrokParseStatusItem]
    total: int


router = APIRouter()
logger = Logger()

STATIC_GROK_PARSING_TASKS: Dict[str, Any] = {}


def update_static_grok_task_status(
    task_id: str,
    status: str,
    detail: str = "",
    completed: bool = False,
    error: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
):
    task_entry = STATIC_GROK_PARSING_TASKS.get(task_id, {})
    task_entry.update(
        {
            "status": status,
            "progress_detail": detail,
            "completed": completed,
            "error": error,
            "last_updated": datetime.now().isoformat(),
        }
    )
    if result_summary:
        task_entry["result_summary"] = result_summary
    STATIC_GROK_PARSING_TASKS[task_id] = task_entry
    logger.debug(
        f"Static Grok Parsing Task {task_id} status updated: {status} - {detail}"
    )


def _run_static_grok_parse_background(
    task_id: str, request_params: StaticGrokRunRequest
):
    group_name_str = (
        f"group '{request_params.group_name}'"
        if request_params.group_name
        else "ALL groups" if request_params.all_groups else "UNKNOWN selection"
    )
    update_static_grok_task_status(
        task_id,
        "Initializing",
        f"Preparing for static Grok parsing of {group_name_str}",
    )

    actual_patterns_file_to_use: str  # Will be set from request_params

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            raise ConnectionError("Elasticsearch not available.")

        path_on_server = request_params.grok_patterns_file_path_on_server
        if not os.path.isabs(path_on_server):
            raise ValueError(
                f"Provided Grok patterns file path '{path_on_server}' on server must be absolute."
            )
        if not os.path.exists(path_on_server):
            raise FileNotFoundError(
                f"Specified Grok patterns file on server not found: {path_on_server}"
            )
        actual_patterns_file_to_use = path_on_server
        logger.info(
            f"Task {task_id}: Using server-specified Grok patterns file: {actual_patterns_file_to_use}"
        )

        agent = StaticGrokParserAgent(
            db=db, grok_patterns_yaml_path=actual_patterns_file_to_use
        )

        groups_to_clear_param: Optional[List[str]] = None
        clear_all_param: bool = False

        if request_params.clear_previous_results:
            if request_params.all_groups:
                clear_all_param = True
            elif request_params.group_name:
                groups_to_clear_param = [request_params.group_name]

        update_static_grok_task_status(
            task_id, "Running", f"Parsing {group_name_str}..."
        )
        final_state = agent.run(
            clear_records_for_groups=groups_to_clear_param,
            clear_all_group_records=clear_all_param,
        )

        summary_for_task: Dict[str, Any] = {
            "orchestrator_status": final_state.get("orchestrator_status"),
            "orchestrator_errors": final_state.get("orchestrator_error_messages", []),
            "groups_summary": {},
        }
        for gn, g_data in final_state.get("overall_group_results", {}).items():
            summary_for_task["groups_summary"][gn] = {
                "status": g_data.get("group_status"),
                "errors": g_data.get("group_error_messages", []),
                "files_processed_count": len(
                    g_data.get("files_processed_summary_this_run", {})
                ),
            }
        update_static_grok_task_status(
            task_id,
            "Completed",
            f"Static Grok parsing for {group_name_str} finished.",
            completed=True,
            result_summary=summary_for_task,
        )

    except Exception as e:
        err_msg = f"Error during static Grok parsing task: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_static_grok_task_status(
            task_id, "Error", err_msg, completed=True, error=err_msg
        )


@router.post("/run", response_model=TaskInfo)
async def run_static_grok_parser(
    request: StaticGrokRunRequest, background_tasks: BackgroundTasks
):
    if not request.group_name and not request.all_groups:
        raise HTTPException(
            status_code=400,
            detail="Either 'group_name' or 'all_groups' must be specified.",
        )
    if request.group_name and request.all_groups:
        raise HTTPException(
            status_code=400, detail="Cannot specify both 'group_name' and 'all_groups'."
        )

    task_id = str(uuid.uuid4())
    STATIC_GROK_PARSING_TASKS[task_id] = {
        "status": "Pending",
        "progress_detail": "",
        "completed": False,
        "error": None,
        "last_updated": datetime.now().isoformat(),
        "result_summary": None,
    }
    background_tasks.add_task(_run_static_grok_parse_background, task_id, request)
    return TaskInfo(task_id=task_id, message="Static Grok parsing process initiated.")


@router.get("/task-status/{task_id}")
async def get_static_grok_task_status(task_id: str):
    task_info = STATIC_GROK_PARSING_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(
            status_code=404, detail="Static Grok Parse Task ID not found."
        )
    return JSONResponse(content=task_info)


@router.get("/list-status", response_model=StaticGrokStatusListResponse)
async def list_static_grok_statuses(group_name: Optional[str] = None):
    db = ElasticsearchDatabase()
    if db.instance is None:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")
    es_service = ElasticsearchDataService(db)

    status_entries_sources = es_service.get_all_status_entries(group_name=group_name)

    response_items = [
        StaticGrokParseStatusItem(**source) for source in status_entries_sources
    ]
    return StaticGrokStatusListResponse(
        statuses=response_items, total=len(response_items)
    )


@router.post("/delete-parsed-data", response_model=MessageResponse)
async def delete_static_grok_parsed_data(request: StaticGrokDeleteRequest):
    if not request.group_name and not request.all_groups:
        raise HTTPException(
            status_code=400,
            detail="Either 'group_name' or 'all_groups' must be specified for deletion.",
        )
    if request.group_name and request.all_groups:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both 'group_name' and 'all_groups' for deletion.",
        )

    db = ElasticsearchDatabase()
    if db.instance is None:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    # For deletion, the agent doesn't strictly need to *parse* patterns,
    # but its constructor loads GrokPatternService.
    # Pass a dummy path, as the actual patterns won't be used for deletion logic.
    dummy_patterns_file_for_agent_init = "dummy_patterns_for_delete.yaml"
    logger.warning(
        f"Initializing StaticGrokParserAgent for delete operation with dummy patterns path: '{dummy_patterns_file_for_agent_init}'. This path is not used for deletion itself."
    )

    agent = StaticGrokParserAgent(
        db=db, grok_patterns_yaml_path=dummy_patterns_file_for_agent_init
    )
    # es_service = agent.es_service # agent.es_service is already available

    groups_to_delete: List[str] = []
    if request.all_groups:
        groups_to_delete = agent.es_service.get_all_log_group_names()
        if not groups_to_delete:
            return MessageResponse(
                message="No groups found in the system to delete data for."
            )
    elif request.group_name:
        groups_to_delete = [request.group_name]

    deleted_count = 0
    errors_count = 0
    error_messages: List[str] = []

    for group_name_to_delete in groups_to_delete:
        try:
            logger.info(f"API: Clearing data for group: {group_name_to_delete}")
            agent._clear_group_data(group_name_to_delete)
            deleted_count += 1
        except Exception as e:
            logger.error(
                f"API: Error clearing data for group '{group_name_to_delete}': {e}",
                exc_info=True,
            )
            errors_count += 1
            error_messages.append(f"Failed to clear {group_name_to_delete}: {str(e)}")

    if errors_count > 0:
        detail_msg = f"Data deletion process completed with {errors_count} error(s). Groups affected: {deleted_count - errors_count} successful. Errors: {'; '.join(error_messages)}"
        return MessageResponse(message=detail_msg)

    return MessageResponse(
        message=f"Successfully cleared parsed data and status for {deleted_count} group(s)."
    )

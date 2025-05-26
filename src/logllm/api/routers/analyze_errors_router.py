# src/logllm/api/routers/analyze_errors_router.py
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ...agents.error_summarizer import ErrorSummarizerAgent
from ...config import config as cfg
from ...utils.database import ElasticsearchDatabase
from ...utils.logger import Logger
from ..models.analyze_errors_models import (
    AnalyzeErrorsRunParams,
    AnalyzeErrorsTaskStatusResponse,
    ErrorSummaryListItem,
    ListErrorSummariesResponse,
    TaskInitiationResponse,
)

router = APIRouter()
logger = Logger()

# In-memory task store (for production, use Redis, Celery results backend, or a DB)
ERROR_ANALYSIS_TASKS: Dict[str, Any] = {}


def update_error_analysis_task_status(
    task_id: str,
    status: str,
    detail: Optional[str] = None,
    completed: bool = False,
    error: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
):
    if task_id not in ERROR_ANALYSIS_TASKS:
        ERROR_ANALYSIS_TASKS[task_id] = {}  # Initialize if not present

    ERROR_ANALYSIS_TASKS[task_id]["status"] = status
    ERROR_ANALYSIS_TASKS[task_id]["progress_detail"] = detail
    ERROR_ANALYSIS_TASKS[task_id]["completed"] = completed
    ERROR_ANALYSIS_TASKS[task_id]["error"] = error
    ERROR_ANALYSIS_TASKS[task_id]["last_updated"] = datetime.utcnow().isoformat() + "Z"
    if result_summary:
        ERROR_ANALYSIS_TASKS[task_id]["result_summary"] = result_summary
    logger.debug(
        f"Error Analysis Task {task_id} status updated: {status} - {detail or ''}"
    )


def run_error_summarizer_background_task(task_id: str, params: AnalyzeErrorsRunParams):
    update_error_analysis_task_status(
        task_id,
        "Initializing",
        f"Preparing error analysis for group '{params.group_name}' from {params.start_time_iso} to {params.end_time_iso}.",
    )
    logger.info(
        f"Task {task_id}: Background Error Summarizer task started for group '{params.group_name}'."
    )

    try:
        db = ElasticsearchDatabase()
        if not db.instance:
            err_msg = "Elasticsearch not available for error analysis task."
            logger.error(f"Task {task_id}: {err_msg}")
            update_error_analysis_task_status(
                task_id, "Failed", err_msg, completed=True, error=err_msg
            )
            return

        # Agent initialization might create its own LLM instance if not passed one
        # For API, it's cleaner if agent uses configured defaults unless specific model is passed via params.
        # Here, we rely on the agent's internal logic to pick/use the LLM model.
        agent = ErrorSummarizerAgent(
            db=db
        )  # LLM instance will be created inside agent if needed

        update_error_analysis_task_status(
            task_id, "Running", "Agent processing logs..."
        )

        final_state = agent.run(
            group_name=params.group_name,
            start_time_iso=params.start_time_iso,
            end_time_iso=params.end_time_iso,
            error_log_levels=params.error_log_levels,
            max_logs_to_process=params.max_logs_to_process,
            embedding_model_name=params.embedding_model_name,
            llm_model_for_summary=params.llm_model_for_summary,
            clustering_params={
                "eps": params.dbscan_eps,
                "min_samples": params.dbscan_min_samples,
            },
            sampling_params={
                "max_samples_per_cluster": params.max_samples_per_cluster,
                "max_samples_unclustered": params.max_samples_unclustered,
            },
            target_summary_index=params.target_summary_index,
        )

        # For the task status, we primarily want the agent's final status and processed details
        api_result_summary = {
            "agent_status": final_state.get("agent_status"),
            "processed_cluster_details": final_state.get(
                "processed_cluster_details", []
            ),
            "final_summary_ids_count": len(final_state.get("final_summary_ids", [])),
            "errors_during_run": final_state.get("error_messages", []),
            "raw_logs_fetched_count": len(final_state.get("raw_error_logs", [])),
        }

        success_msg = f"Error analysis task for group '{params.group_name}' finished with agent status: {final_state.get('agent_status')}."
        logger.info(f"Task {task_id}: {success_msg}")
        update_error_analysis_task_status(
            task_id,
            str(
                final_state.get("agent_status", "Completed")
            ),  # Use agent's final status
            success_msg,
            completed=True,
            result_summary=api_result_summary,
            error=(
                "; ".join(final_state.get("error_messages", []))
                if final_state.get("error_messages")
                else None
            ),
        )

    except Exception as e:
        err_msg = f"Critical error during Error Summarizer background task: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_error_analysis_task_status(
            task_id, "Failed", err_msg, completed=True, error=err_msg
        )


@router.post("/run-summary", response_model=TaskInitiationResponse)
async def run_error_summary_analysis(
    params: AnalyzeErrorsRunParams, background_tasks: BackgroundTasks
):
    """
    Initiates the error log summarization process for a given group and time window.
    """
    task_id = str(uuid.uuid4())
    ERROR_ANALYSIS_TASKS[task_id] = {
        "status": "Pending",
        "progress_detail": "Task submitted to queue.",
        "completed": False,
        "error": None,
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "result_summary": None,
        "params_used": params.model_dump(),  # Store params for reference
    }

    background_tasks.add_task(run_error_summarizer_background_task, task_id, params)

    return TaskInitiationResponse(
        task_id=task_id,
        message=f"Error log summarization task initiated for group '{params.group_name}'. Monitor status with task ID.",
    )


@router.get("/task-status/{task_id}", response_model=AnalyzeErrorsTaskStatusResponse)
async def get_error_analysis_task_status(task_id: str):
    """
    Retrieves the status of a previously initiated error analysis task.
    """
    task_info = ERROR_ANALYSIS_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Error Analysis Task ID not found.")
    return AnalyzeErrorsTaskStatusResponse(task_id=task_id, **task_info)


@router.get("/list-summaries", response_model=ListErrorSummariesResponse)
async def list_generated_error_summaries(
    group_name: Optional[str] = Query(
        None, description="Filter summaries by group name."
    ),
    start_time: Optional[str] = Query(
        None,
        description="Filter summaries generated after this ISO timestamp (inclusive).",
    ),
    end_time: Optional[str] = Query(
        None,
        description="Filter summaries generated before this ISO timestamp (inclusive).",
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of summaries to return."),
    offset: int = Query(0, ge=0, description="Offset for pagination."),
    sort_by: str = Query("generation_timestamp", description="Field to sort by."),
    sort_order: str = Query("desc", description="Sort order: 'asc' or 'desc'."),
):
    """
    Lists previously generated error summaries from the storage index.
    """
    db = ElasticsearchDatabase()
    if not db.instance or not db.instance.indices.exists(
        index=cfg.INDEX_ERROR_SUMMARIES
    ):
        logger.info(
            f"Summary index '{cfg.INDEX_ERROR_SUMMARIES}' does not exist. Returning empty list."
        )
        return ListErrorSummariesResponse(
            summaries=[], total=0, offset=offset, limit=limit
        )

    bool_query: Dict[str, List[Any]] = {"must": [], "filter": []}
    if group_name:
        bool_query["filter"].append({"term": {"group_name.keyword": group_name}})

    time_range_filter = {}
    if start_time:
        try:
            validate_iso_format(start_time)  # Validate format
            time_range_filter["gte"] = start_time
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid start_time format: {e}"
            )
    if end_time:
        try:
            validate_iso_format(end_time)  # Validate format
            time_range_filter["lte"] = end_time
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid end_time format: {e}")

    if time_range_filter:
        bool_query["filter"].append(
            {"range": {"generation_timestamp": time_range_filter}}
        )

    es_query_body: Dict[str, Any] = {
        "query": (
            {"bool": bool_query}
            if bool_query["must"] or bool_query["filter"]
            else {"match_all": {}}
        ),
        "size": limit,
        "from": offset,
        "sort": [{sort_by: {"order": sort_order}}],
    }

    try:
        logger.debug(f"Listing error summaries with query: {es_query_body}")
        count_response = db.instance.count(
            index=cfg.INDEX_ERROR_SUMMARIES, body={"query": es_query_body["query"]}
        )
        total_hits = count_response.get("count", 0)

        if total_hits == 0:
            return ListErrorSummariesResponse(
                summaries=[], total=0, offset=offset, limit=limit
            )

        search_response = db.instance.search(
            index=cfg.INDEX_ERROR_SUMMARIES, body=es_query_body
        )

        summaries_data = []
        for hit in search_response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            source["_id"] = hit.get("_id")  # Add ES document ID
            summaries_data.append(ErrorSummaryListItem.model_validate(source))

        return ListErrorSummariesResponse(
            summaries=summaries_data, total=total_hits, offset=offset, limit=limit
        )

    except Exception as e:
        logger.error(f"Error listing error summaries: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to list error summaries: {str(e)}"
        )

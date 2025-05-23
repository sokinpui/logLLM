import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from ...utils.logger import Logger
from ...utils.database import ElasticsearchDatabase
from ...utils.llm_model import GeminiModel
from ...utils.prompts_manager import PromptsManager
from ...config import config as cfg
from ...agents.es_parser_agent import (
    AllGroupsParserAgent,
    SingleGroupParserAgent,
    AllGroupsParserState,
    SingleGroupParseGraphState,
)
from ..models.es_parse_models import (
    EsParseRunRequest,
    EsParseResultItem,
    EsParseListResponse,
    EsParseGroupListResponse,
    TaskStatusResponse,
    MessageResponse,
)

router = APIRouter()
logger = Logger()

# --- Task Management (In-memory, similar to collect_router) ---
PARSING_TASKS: Dict[str, Any] = {}


def update_parsing_task_status(
    task_id: str,
    status: str,
    detail: str = "",
    completed: bool = False,
    error: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
):
    if task_id not in PARSING_TASKS:
        PARSING_TASKS[task_id] = {}
    PARSING_TASKS[task_id]["status"] = status
    PARSING_TASKS[task_id]["progress_detail"] = detail
    PARSING_TASKS[task_id]["completed"] = completed
    PARSING_TASKS[task_id]["error"] = error
    PARSING_TASKS[task_id]["last_updated"] = datetime.now().isoformat()
    if result_summary:
        PARSING_TASKS[task_id]["result_summary"] = result_summary
    logger.debug(f"ES Parsing Task {task_id} status updated: {status} - {detail}")


def run_es_parse_task_with_status(task_id: str, request_params: EsParseRunRequest):
    group_name_str = (
        f"group '{request_params.group_name}'"
        if request_params.group_name
        else "ALL groups"
    )
    update_parsing_task_status(
        task_id, "Initializing", f"Preparing to parse {group_name_str}"
    )
    logger.info(f"Task {task_id}: Background ES parsing started for {group_name_str}")

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            err_msg = "Elasticsearch not available."
            logger.error(f"Task {task_id}: {err_msg}")
            update_parsing_task_status(
                task_id, "Error", err_msg, completed=True, error=err_msg
            )
            return

        # Determine PromptsManager path (this assumes API runs where default path is valid)
        # For more complex setups, this path might need to be configurable for the API.
        # The PromptsManager itself has fallback logic to find prompts relative to its own location.
        prompts_manager = PromptsManager()  # Uses default prompts.json
        model = GeminiModel()

        final_state: Optional[Dict[str, Any]] = None  # To store the result state

        if request_params.group_name:
            update_parsing_task_status(
                task_id,
                "Running",
                f"Instantiating SingleGroupParserAgent for {request_params.group_name}",
            )
            agent = SingleGroupParserAgent(
                model=model, db=db, prompts_manager=prompts_manager
            )
            single_group_config: Dict[str, Any] = {
                "group_name": request_params.group_name,
                "field_to_parse": request_params.field_to_parse,
                "fields_to_copy": request_params.copy_fields,
                "batch_size": request_params.batch_size,
                "sample_size_generation": request_params.sample_size_generation,
                "sample_size_validation": request_params.validation_sample_size,
                "validation_threshold": request_params.validation_threshold,
                "max_regeneration_attempts": request_params.max_retries
                + 1,  # Agent expects max *attempts*
                "provided_grok_pattern": request_params.pattern,
                "keep_unparsed_index": request_params.keep_unparsed_index,
            }
            final_state = agent.run(single_group_config)
            task_result_summary = {request_params.group_name: final_state}

        else:  # All groups
            update_parsing_task_status(
                task_id, "Running", "Instantiating AllGroupsParserAgent"
            )
            agent = AllGroupsParserAgent(
                model=model, db=db, prompts_manager=prompts_manager
            )
            initial_orchestrator_state: AllGroupsParserState = {
                "group_info_index": cfg.INDEX_GROUP_INFOS,
                "field_to_parse": request_params.field_to_parse,
                "fields_to_copy": request_params.copy_fields,
                "group_results": {},
                "status": "pending",
            }
            final_state = agent.run(
                initial_state=initial_orchestrator_state,
                num_threads=request_params.threads,
                batch_size=request_params.batch_size,
                sample_size=request_params.sample_size_generation,
                validation_sample_size=request_params.validation_sample_size,
                validation_threshold=request_params.validation_threshold,
                max_regeneration_attempts=request_params.max_retries + 1,
                keep_unparsed_index=request_params.keep_unparsed_index,
                # provided_grok_pattern is None for all groups run
            )
            task_result_summary = final_state.get("group_results", {})

        success_msg = f"ES parsing for {group_name_str} finished."
        logger.info(f"Task {task_id}: {success_msg}")
        update_parsing_task_status(
            task_id,
            "Completed",
            success_msg,
            completed=True,
            result_summary=task_result_summary,
        )

    except Exception as e:
        err_msg = f"Error during ES parsing task: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_parsing_task_status(
            task_id, "Error", err_msg, completed=True, error=err_msg
        )


@router.post("/run", response_model=MessageResponse)
async def run_es_parser(request: EsParseRunRequest, background_tasks: BackgroundTasks):
    group_name_str = (
        f"group '{request.group_name}'" if request.group_name else "ALL groups"
    )
    logger.info(f"Request to start ES parsing for {group_name_str}")

    if request.pattern and not request.group_name:
        raise HTTPException(
            status_code=400,
            detail="The --pattern argument requires the --group_name argument to be specified.",
        )

    task_id = str(uuid.uuid4())
    PARSING_TASKS[task_id] = {
        "status": "Pending",
        "progress_detail": "",
        "completed": False,
        "error": None,
        "last_updated": datetime.now().isoformat(),
        "result_summary": None,
    }

    background_tasks.add_task(run_es_parse_task_with_status, task_id, request)

    logger.info(f"Task {task_id}: ES parsing for {group_name_str} initiated.")
    return MessageResponse(
        message=f"ES parsing initiated for {group_name_str}. Task ID: {task_id}"
    )


@router.get("/task-status/{task_id}", response_model=TaskStatusResponse)
async def get_es_parse_task_status(task_id: str):
    task_info = PARSING_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="ES Parse Task ID not found.")
    return TaskStatusResponse(task_id=task_id, **task_info)


@router.get("/list-results", response_model=EsParseListResponse)
async def list_es_parse_results(
    group: Optional[str] = None,
    all_history: bool = False,
    # latest: Optional[int] = None, # 'latest' implies specific count, 'all_history' or specific group is clearer
):
    logger.info(f"Listing ES parse results: group={group}, all_history={all_history}")
    history_index = cfg.INDEX_GROK_RESULTS_HISTORY
    db = ElasticsearchDatabase()
    if db.instance is None:
        raise HTTPException(status_code=503, detail="Elasticsearch not available.")
    if not db.instance.indices.exists(index=history_index):
        return EsParseListResponse(results=[], total=0)

    results_hits: List[Dict[str, Any]] = []
    search_params: Dict[str, Any] = {"index": history_index}
    group_field_keyword = "group_name.keyword"

    if group:
        search_params["body"] = {
            "query": {"term": {group_field_keyword: group}},
            "sort": [{"timestamp": "desc"}],
        }
        search_params["size"] = (
            1000 if all_history else 1
        )  # Fetch more if all history for a group
    elif all_history:
        search_params["body"] = {
            "query": {"match_all": {}},
            "sort": [{group_field_keyword: "asc"}, {"timestamp": "desc"}],
        }
        search_params["size"] = 10000  # Cap for all history
    else:  # Default: Latest result for each group
        search_params["body"] = {
            "size": 0,
            "aggs": {
                "groups": {
                    "terms": {"field": group_field_keyword, "size": 1000},
                    "aggs": {
                        "latest_entry": {
                            "top_hits": {
                                "size": 1,
                                "sort": [{"timestamp": {"order": "desc"}}],
                                "_source": {"includes": ["*"]},
                            }
                        }
                    },
                }
            },
        }
        response = await db.instance.search(
            **search_params
        )  # Use await for async ES client if available, or adapt
        temp_results = []
        for bucket in (
            response.get("aggregations", {}).get("groups", {}).get("buckets", [])
        ):
            latest_hit = (
                bucket.get("latest_entry", {}).get("hits", {}).get("hits", [{}])[0]
            )
            if latest_hit:
                temp_results.append(latest_hit)
        results_hits = sorted(
            temp_results, key=lambda x: x.get("_source", {}).get("group_name", "")
        )

    if not group_field_keyword in search_params["body"].get("aggs", {}).get(
        "groups", {}
    ).get("terms", {}).get(
        "field", ""
    ):  # If not aggregation query
        response = await db.instance.search(**search_params)
        results_hits = response["hits"]["hits"]

    output_results: List[EsParseResultItem] = []
    for hit in results_hits:
        doc_source = hit.get("_source", {})
        group_name = doc_source.get("group_name", "N/A")
        processed = doc_source.get("processed_count", 0)
        successful = doc_source.get("successful_count", 0)

        success_percentage = None
        if processed > 0:
            success_percentage = round((successful / processed) * 100, 2)

        # Reconstruct error messages if available (example, adjust if stored differently)
        # agent_errors = doc_source.get("agent_error_messages", [])
        # For now, we use the count. If full messages are stored in history, they can be added.

        item = EsParseResultItem(
            group_name=group_name,
            parsing_status=doc_source.get("parsing_status", "unknown"),
            grok_pattern_used=doc_source.get("grok_pattern_used"),
            timestamp=doc_source.get("timestamp", ""),
            processed_count=processed,
            successful_count=successful,
            failed_count=doc_source.get("failed_count", 0),
            parse_error_count=doc_source.get("parse_error_count", 0),
            index_error_count=doc_source.get("index_error_count", 0),
            agent_error_count=doc_source.get("agent_error_count", 0),
            target_index=cfg.get_parsed_log_storage_index(group_name),
            unparsed_index=cfg.get_unparsed_log_storage_index(group_name),
            success_percentage=success_percentage,
            # error_messages_summary=agent_errors[:3] if agent_errors else None # Example
        )
        output_results.append(item)

    return EsParseListResponse(results=output_results, total=len(output_results))


@router.get("/list-groups", response_model=EsParseGroupListResponse)
async def list_es_parse_groups():
    logger.info("Fetching unique group names from ES parse history.")
    history_index = cfg.INDEX_GROK_RESULTS_HISTORY
    db = ElasticsearchDatabase()
    if db.instance is None:
        raise HTTPException(status_code=503, detail="Elasticsearch not available.")
    if not db.instance.indices.exists(index=history_index):
        return EsParseGroupListResponse(groups=[], total=0)

    group_field_keyword = "group_name.keyword"
    try:
        response = (
            await db.instance.search(  # Use await for async ES client if available
                index=history_index,
                size=0,
                aggs={
                    "unique_groups": {
                        "terms": {"field": group_field_keyword, "size": 10000}
                    }
                },
            )
        )
        group_names = [
            bucket["key"]
            for bucket in response.get("aggregations", {})
            .get("unique_groups", {})
            .get("buckets", [])
        ]
        group_names.sort()
        return EsParseGroupListResponse(groups=group_names, total=len(group_names))
    except Exception as e:
        logger.error(
            f"Error fetching unique group names for ES parse: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Error fetching group names: {str(e)}"
        )

# src/logllm/api/collect_router.py

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime  # <--- Moved to top
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...utils.collector import Collector
from ...utils.database import ElasticsearchDatabase
from ...utils.logger import Logger
from ..models.collect_models import (
    CollectRequest,
    DirectoryAnalysisResponse,
    GroupInfoModel,
)
from ..models.common_models import MessageResponse

router = APIRouter()
logger = Logger()


# --- Endpoint for analyzing server path structure ---
@router.post("/analyze-structure", response_model=DirectoryAnalysisResponse)
async def analyze_server_directory_structure(request: CollectRequest):
    logger.info(f"Analyzing structure for server directory: {request.directory}")
    directory = request.directory

    if not os.path.exists(directory):
        logger.warning(f"Directory for analysis not found: {directory}")
        return DirectoryAnalysisResponse(
            path_exists=False,
            root_files_present=False,
            identified_groups=[],
            error_message="Directory not found on server.",
            scanned_path=directory,
        )
    if not os.path.isdir(directory):
        logger.warning(f"Path for analysis is not a directory: {directory}")
        return DirectoryAnalysisResponse(
            path_exists=True,
            root_files_present=False,
            identified_groups=[],
            error_message="Path exists but is not a directory.",
            scanned_path=directory,
        )

    root_files_present = False
    identified_groups_dict = {}

    try:
        base_selected_folder_name = os.path.basename(directory.rstrip("/\\"))

        for item_name in os.listdir(directory):
            item_path = os.path.join(directory, item_name)
            if item_name.startswith("."):
                continue

            if os.path.isfile(item_path) and item_name.lower().endswith(
                (".log", ".txt", ".gz")
            ):
                root_files_present = True
            elif os.path.isdir(item_path):
                group_name = item_name
                file_count = 0
                for _, _, files_in_group in os.walk(item_path):
                    for f_name in files_in_group:
                        if f_name.lower().endswith((".log", ".txt", ".gz")):
                            file_count += 1
                if file_count > 0:
                    identified_groups_dict[group_name] = file_count

        identified_groups_list = [
            GroupInfoModel(name=name, file_count=count)
            for name, count in identified_groups_dict.items()
        ]

        logger.info(
            f"Analysis for {directory}: Root files: {root_files_present}, Groups: {len(identified_groups_list)}"
        )
        return DirectoryAnalysisResponse(
            path_exists=True,
            root_files_present=root_files_present,
            identified_groups=identified_groups_list,
            scanned_path=directory,
        )

    except Exception as e:
        logger.error(f"Error analyzing directory {directory}: {e}", exc_info=True)
        return DirectoryAnalysisResponse(
            path_exists=True,
            root_files_present=False,
            identified_groups=[],
            error_message=f"Error during server-side analysis: {str(e)}",
            scanned_path=directory,
        )


# --- Task Management (In-memory for simplicity, use Redis/DB for production) ---
COLLECTION_TASKS = {}


def update_task_status(
    task_id: str,
    status: str,
    detail: str = "",
    completed: bool = False,
    error: Optional[str] = None,
):
    if task_id not in COLLECTION_TASKS:
        COLLECTION_TASKS[task_id] = {}
    COLLECTION_TASKS[task_id]["status"] = status
    COLLECTION_TASKS[task_id]["progress_detail"] = detail
    COLLECTION_TASKS[task_id]["completed"] = completed
    COLLECTION_TASKS[task_id]["error"] = error
    COLLECTION_TASKS[task_id][
        "last_updated"
    ] = datetime.now().isoformat()  # datetime is now imported at top
    logger.debug(f"Task {task_id} status updated: {status} - {detail}")


# --- Background collection task (modified for status updates) ---
def run_server_path_collection_task_with_status(task_id: str, directory: str):
    update_task_status(
        task_id, "Initializing", f"Preparing to collect from {directory}"
    )
    logger.info(
        f"Task {task_id}: Background collection started for server path: {directory}"
    )
    try:
        if not os.path.isdir(directory):
            err_msg = f"Directory not found: {directory}"
            logger.error(f"Task {task_id}: {err_msg}")
            update_task_status(task_id, "Error", err_msg, completed=True, error=err_msg)
            return

        es_db = ElasticsearchDatabase()
        if es_db.instance is None:
            err_msg = "Elasticsearch not available."
            logger.error(f"Task {task_id}: {err_msg}")
            update_task_status(task_id, "Error", err_msg, completed=True, error=err_msg)
            return

        update_task_status(
            task_id, "Scanning directory", f"Collector initializing for {directory}"
        )
        # Collector instantiation also updates group_infos in its __init__
        # It will now use the corrected LogFile ID logic
        collector = Collector(directory)

        if not collector.collected_files:
            logger.info(f"Task {task_id}: No log files found in {directory}.")
            update_task_status(
                task_id, "Completed", "No log files found to collect.", completed=True
            )
            return

        update_task_status(
            task_id,
            "Processing",
            f"Found {len(collector.collected_files)} files. Starting insertion.",
        )
        logger.info(
            f"Task {task_id}: Collector found {len(collector.collected_files)} files. Starting insertion..."
        )

        # This call will use the corrected logic in collector.py
        collector.insert_very_large_logs_into_db(
            db=es_db, files=collector.collected_files
        )

        success_msg = f"Log collection and insertion from {directory} finished."
        logger.info(f"Task {task_id}: {success_msg}")
        update_task_status(task_id, "Completed", success_msg, completed=True)

    except Exception as e:
        err_msg = f"Error during collection: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_task_status(task_id, "Error", err_msg, completed=True, error=err_msg)


# --- Endpoint to start collection from server path & get task ID ---
@router.post("/from-server-path", response_model=MessageResponse)
async def start_collection_from_server_path(
    request: CollectRequest, background_tasks: BackgroundTasks
):
    logger.info(f"Request to start collection from server path: {request.directory}")

    if not os.path.isdir(request.directory):
        logger.error(f"Directory not found for collection: {request.directory}")
        raise HTTPException(
            status_code=400,
            detail=f"Directory not found on server: {request.directory}",
        )

    task_id = str(uuid.uuid4())
    COLLECTION_TASKS[task_id] = {
        "status": "Pending",
        "progress_detail": "",
        "completed": False,
        "error": None,
        "last_updated": datetime.now().isoformat(),  # datetime imported at top
    }

    background_tasks.add_task(
        run_server_path_collection_task_with_status, task_id, request.directory
    )

    logger.info(
        f"Task {task_id}: Collection from server path {request.directory} initiated."
    )
    # Add task_id to the response message, so frontend can use it immediately
    return MessageResponse(
        message=f"Collection initiated for '{request.directory}'. Task ID: {task_id}",
        # task_id=task_id # Pydantic model MessageResponse doesn't have task_id, but it's in the message string
    )


# --- Endpoint to get task status ---
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress_detail: Optional[str] = None
    completed: bool
    error: Optional[str] = None
    last_updated: Optional[str] = None


@router.get("/task-status/{task_id}", response_model=TaskStatusResponse)
async def get_collection_task_status(task_id: str):
    task_info = COLLECTION_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="Task ID not found.")
    return TaskStatusResponse(task_id=task_id, **task_info)


# --- /upload-and-process endpoint (modified for task status) ---
def run_uploaded_collection_task_with_status(task_id: str, temp_server_path: str):
    update_task_status(
        task_id,
        "Initializing",
        f"Preparing for uploaded logs in {os.path.basename(temp_server_path)}",
    )
    logger.info(
        f"Task {task_id}: Background collection started for uploaded logs from: {temp_server_path}"
    )
    try:
        es_db = ElasticsearchDatabase()
        if es_db.instance is None:
            err_msg = "Elasticsearch not available."
            logger.error(f"Task {task_id}: {err_msg}")
            update_task_status(task_id, "Error", err_msg, completed=True, error=err_msg)
            return

        update_task_status(
            task_id,
            "Scanning directory",
            f"Collector initializing for {temp_server_path}",
        )
        collector = Collector(
            temp_server_path
        )  # Corrected LogFile ID logic will be used

        if not collector.collected_files:
            logger.info(
                f"Task {task_id}: No log files found in uploaded structure: {temp_server_path}"
            )
            update_task_status(
                task_id,
                "Completed",
                "No log files found in uploaded content.",
                completed=True,
            )
            return

        update_task_status(
            task_id,
            "Processing",
            f"Found {len(collector.collected_files)} uploaded files. Starting insertion.",
        )
        logger.info(
            f"Task {task_id}: Collector found {len(collector.collected_files)} uploaded files. Starting insertion..."
        )

        collector.insert_very_large_logs_into_db(  # Corrected logic will be used
            db=es_db, files=collector.collected_files
        )

        success_msg = f"Collection and insertion from uploaded folder finished."
        logger.info(f"Task {task_id}: {success_msg}")
        update_task_status(task_id, "Completed", success_msg, completed=True)

    except Exception as e:
        err_msg = f"Error during collection of uploaded files: {str(e)}"
        logger.error(f"Task {task_id}: {err_msg}", exc_info=True)
        update_task_status(task_id, "Error", err_msg, completed=True, error=err_msg)
    finally:
        pass


@router.post("/upload-and-process", response_model=MessageResponse)
async def upload_and_process_folder(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    relative_paths_json: str = Form(...),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    try:
        relative_paths: List[str] = json.loads(relative_paths_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="Invalid format for relative_paths_json."
        )

    if len(files) != len(relative_paths):
        raise HTTPException(
            status_code=400,
            detail="Mismatch between number of files and decoded relative paths.",
        )

    task_id = str(uuid.uuid4())
    temp_upload_path = os.path.join(tempfile.gettempdir(), f"logllm_upload_{task_id}")
    os.makedirs(temp_upload_path, exist_ok=True)
    logger.info(
        f"Task {task_id}: Created temporary directory for upload: {temp_upload_path}"
    )

    COLLECTION_TASKS[task_id] = {
        "status": "Uploading files",
        "progress_detail": "",
        "completed": False,
        "error": None,
        "last_updated": datetime.now().isoformat(),  # datetime imported at top
    }

    try:
        for i, file_obj in enumerate(files):
            original_relative_path = relative_paths[i]
            path_parts = original_relative_path.split("/")
            if not path_parts:
                continue

            path_inside_selected_folder = os.path.join(*path_parts[1:])

            if ".." in path_inside_selected_folder or os.path.isabs(
                path_inside_selected_folder
            ):
                logger.warning(
                    f"Task {task_id}: Invalid path {original_relative_path}. Skipping file: {file_obj.filename}"
                )
                continue

            destination_path = os.path.join(
                temp_upload_path, path_inside_selected_folder
            )
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            with open(destination_path, "wb") as buffer:
                shutil.copyfileobj(file_obj.file, buffer)
            logger.debug(f"Task {task_id}: Saved uploaded file to: {destination_path}")

        update_task_status(
            task_id, "Upload complete", "Files saved to server, preparing collection."
        )

        def collection_and_cleanup_task(current_task_id: str, path_to_clean: str):
            try:
                run_uploaded_collection_task_with_status(current_task_id, path_to_clean)
            finally:
                try:
                    if os.path.exists(path_to_clean):
                        shutil.rmtree(path_to_clean)
                        logger.info(
                            f"Task {current_task_id}: Successfully cleaned up temp directory: {path_to_clean}"
                        )
                except Exception as ce:
                    logger.error(
                        f"Task {current_task_id}: Failed to clean up temp directory {path_to_clean}: {ce}",
                        exc_info=True,
                    )

        background_tasks.add_task(
            collection_and_cleanup_task, task_id, temp_upload_path
        )

        logger.info(
            f"Task {task_id}: Collection from uploaded folder initiated. Temp path: {temp_upload_path}"
        )
        # Add task_id to the response message
        return MessageResponse(
            message=f"Files uploaded. Collection initiated (Task ID: {task_id})."
            # task_id=task_id # Pydantic model MessageResponse doesn't have task_id
        )

    except Exception as e:
        logger.error(
            f"Task {task_id}: Error processing uploaded files: {str(e)}", exc_info=True
        )
        if os.path.exists(temp_upload_path):
            shutil.rmtree(temp_upload_path)
            logger.info(
                f"Task {task_id}: Cleaned up temporary directory due to setup error: {temp_upload_path}"
            )
        if task_id in COLLECTION_TASKS:
            del COLLECTION_TASKS[task_id]
        raise HTTPException(
            status_code=500, detail=f"Failed to process uploaded files: {str(e)}"
        )


# Removed: from datetime import datetime  # ensure datetime is imported at the top
# It's now correctly at the top of the file.

from fastapi import APIRouter, HTTPException
from ..models.common_models import MessageResponse
from ..models.collect_models import CollectRequest

# from logllm.utils.collector import Collector
# from logllm.utils.database import ElasticsearchDatabase
import os

router = APIRouter()


@router.post("", response_model=MessageResponse)
async def collect_logs_from_directory(request: CollectRequest):
    # TODO: Implement actual collection logic by calling Collector
    # if not os.path.isdir(request.directory):
    #     raise HTTPException(status_code=400, detail=f"Directory not found: {request.directory}")
    # try:
    #     es_db = ElasticsearchDatabase()
    #     if es_db.instance is None:
    #         raise HTTPException(status_code=503, detail="Elasticsearch not available.")
    #     collector = Collector(request.directory)
    #     if not collector.collected_files:
    #         return MessageResponse(message=f"No log files found in {request.directory} (mock).")
    #     collector.insert_very_large_logs_into_db(db=es_db, files=collector.collected_files)
    #     return MessageResponse(message=f"Log collection from {request.directory} finished (mock).")
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Error during collection: {str(e)} (mock)")
    print(f"Mock collecting logs from: {request.directory}")
    return MessageResponse(
        message=f"Log collection initiated for {request.directory} (mock)."
    )

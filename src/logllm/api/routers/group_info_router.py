# src/logllm/api/routers/group_info_router.py
from typing import List

from fastapi import APIRouter, HTTPException

from ...config import config as cfg
from ...utils.database import ElasticsearchDatabase
from ...utils.logger import Logger
from ..models.group_info_models import GroupInfoDetail, GroupInfoListResponse

router = APIRouter()
logger = Logger()


@router.get("/", response_model=GroupInfoListResponse)
async def list_all_groups_info():
    """
    Retrieves information about all collected groups from the group_infos index.
    """
    db = ElasticsearchDatabase()
    if db.instance is None:
        logger.error("Group Info: Elasticsearch connection failed.")
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    try:
        logger.info(
            f"Group Info: Fetching all groups from index '{cfg.INDEX_GROUP_INFOS}'"
        )
        # Using scroll_search to get all documents, though terms aggregation might be more efficient
        # if we only need unique group names and then fetch details.
        # For now, direct scroll is simpler if INDEX_GROUP_INFOS isn't excessively large.
        query = {"query": {"match_all": {}}}
        group_docs_from_es = db.scroll_search(index=cfg.INDEX_GROUP_INFOS, query=query)

        if not group_docs_from_es:
            logger.info("Group Info: No group information found in the database.")
            return GroupInfoListResponse(groups=[])

        group_details_list: List[GroupInfoDetail] = []
        for doc in group_docs_from_es:
            source = doc.get("_source")
            if (
                source
                and "group" in source
                and "files" in source
                and isinstance(source["files"], list)
            ):
                group_name = source["group"]
                file_count = len(source["files"])
                group_details_list.append(
                    GroupInfoDetail(group_name=group_name, file_count=file_count)
                )
            else:
                logger.warning(
                    f"Group Info: Skipping malformed document in '{cfg.INDEX_GROUP_INFOS}': ID {doc.get('_id')}"
                )

        logger.info(
            f"Group Info: Successfully fetched {len(group_details_list)} groups."
        )
        return GroupInfoListResponse(groups=group_details_list)

    except Exception as e:
        logger.error(
            f"Group Info: Error fetching group information: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch group information: {str(e)}"
        )

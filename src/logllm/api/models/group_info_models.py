# src/logllm/api/models/group_info_models.py
from pydantic import BaseModel
from typing import List


class GroupInfoDetail(BaseModel):
    group_name: str
    file_count: int
    # Example: Add first few file names if desired later
    # sample_files: List[str] = []


class GroupInfoListResponse(BaseModel):
    groups: List[GroupInfoDetail]

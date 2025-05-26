from typing import List, Optional

from pydantic import BaseModel


class CollectRequest(BaseModel):  # For /from-server-path and /analyze-structure
    directory: str


class GroupInfoModel(BaseModel):
    name: str
    file_count: int


class DirectoryAnalysisResponse(BaseModel):
    path_exists: bool
    root_files_present: bool
    identified_groups: List[GroupInfoModel]
    error_message: Optional[str] = None
    scanned_path: str  # To confirm which path was scanned

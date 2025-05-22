from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ContainerStopRequest(BaseModel):
    remove: Optional[bool] = False


class ContainerDetailItem(BaseModel):
    name: str
    status: str
    container_id: Optional[str] = Field(
        None, alias="id"
    )  # Use alias if DockerManager returns 'id'
    short_id: Optional[str] = None
    ports: Optional[List[str]] = []
    mounts: Optional[List[str]] = []


class VolumeDetailItem(BaseModel):
    name: str
    status: str  # e.g., "found", "not_found", "error (api)"
    driver: Optional[str] = None
    mountpoint: Optional[str] = None
    scope: Optional[str] = None


class ContainerStatusResponse(BaseModel):
    statuses: List[ContainerDetailItem]
    volume_info: Optional[VolumeDetailItem] = None

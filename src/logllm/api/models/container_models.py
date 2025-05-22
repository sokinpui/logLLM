from pydantic import BaseModel
from typing import List, Optional


class ContainerStopRequest(BaseModel):
    remove: Optional[bool] = False


class ContainerStatusItem(BaseModel):
    name: str
    status: str


class ContainerStatusResponse(BaseModel):
    statuses: List[ContainerStatusItem]

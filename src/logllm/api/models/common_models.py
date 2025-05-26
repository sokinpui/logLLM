from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str


# Placeholder for complex responses
class GenericResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None

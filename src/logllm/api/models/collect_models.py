from pydantic import BaseModel


class CollectRequest(BaseModel):
    directory: str

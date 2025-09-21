from pydantic import BaseModel
from pydantic import Field


class PicData(BaseModel):
    name: str
    scope: list[str] = Field(default_factory=list)
    url: str
    uploader: str = "unknown"

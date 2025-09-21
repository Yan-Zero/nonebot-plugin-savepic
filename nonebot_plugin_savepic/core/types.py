import numpy as np

from typing import Optional
from pydantic import BaseModel
from pydantic import Field


class PicData(BaseModel):
    id: int
    name: str
    scope: list[str] = Field(default_factory=list)
    url: str
    vec: Optional[np.ndarray] = Field(default_factory=lambda: np.zeros(2048))
    uploader: str = "unknown"

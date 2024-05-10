from pydantic import BaseModel
from enum import Enum


class Config(BaseModel):
    """Plugin Config Here"""

    savepic_admin: list[str] = []
    savepic_dir: str = "savepic"
    savepic_sqlurl: str

    pinecone_apikey: str
    pinecone_index: str = "savepic"
    pinecone_environment: str

    dashscope_api: str
    simpic_enable: bool = False
    simpic_model: str = "one-peach"

    p_model_path: str = "networks/ckpt_epoch_100_rein.pth"
    q_model_path: str = "networks/ckpt_epoch_100_rein.pth.qt.pth"
    # 基于模型的相似度判断

    embedding_sqlurl: str
    black_group: list[str]

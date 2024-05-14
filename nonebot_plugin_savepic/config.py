import os
import json
from pydantic import BaseModel


WORDS = {}
for root, _, files in os.walk("words"):
    for file in files:
        if not file.endswith(".json"):
            continue
        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
            WORDS.update(json.load(f))


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

    notfound_with_jpg: bool = True
    """ randpic 的时候，尝试带 .jpg 再度检索向量 """
    count_per_page_in_list: int = 7
    """ 每页最多多少条 """
    forward_when_listpic: bool = True
    """ listpic 的时候合并转发 """
    max_page_in_listpic: int = 20
    """ 合并转发中所能显示的最大页数 """

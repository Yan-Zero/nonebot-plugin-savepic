from pydantic import BaseModel
from nonebot import get_plugin_config


class Config(BaseModel):
    """Plugin Config Here"""

    savepic_admin: list[str] = []
    savepic_dir: str = "savepic"
    savepic_sqlurl: str

    embedding_key: str
    embedding_url: str
    embedding_model: str

    notfound_with_jpg: bool = True
    """ randpic 的时候，尝试带 .jpg 再度检索向量 """
    count_per_page_in_list: int = 7
    """ 每页最多多少条 """
    forward_when_listpic: bool = True
    """ listpic 的时候合并转发 """
    max_page_in_listpic: int = 20
    """ 合并转发中所能显示的最大页数 """


plugin_config: Config = get_plugin_config(Config)

from nonebot_plugin_datastore import get_plugin_data
from sqlalchemy import TEXT
from sqlalchemy.orm import Mapped, mapped_column

plugin_data = get_plugin_data()
plugin_data.use_global_registry()
Model = plugin_data.Model

class PicData(Model):
    """消息记录"""

    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(TEXT)
    """ 图片名称 """
    group: Mapped[str] = mapped_column(TEXT)
    """ 所属群组 id """

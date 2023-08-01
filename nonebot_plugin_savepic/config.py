from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""
    savepic_admin: list[str] = []
    savepic_dir: str = "savepic"

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Savepic",
    description="表情包保存",
    usage="""用法:
/savepic <文件名> <图片>
/savepic -g <文件名> <全局图片>
/savepic -d <文件名> 删除图图片
/savepic -m <原文件名> <新文件名> 重命名图片
/randpic <关键词> 随机图片
<文件名> 发送图片""",
    config=Config,
    extra={},
)

""" 
This module is used to define the permission of the bot.
"""

from nonebot import get_plugin_config
from nonebot.adapters import Bot, Event
from nonebot.internal.permission import Permission
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN

from .config import Config

plugin_config = get_plugin_config(Config)


class Savepic_Admin(Permission):
    """检查当前事件是否是消息事件且属于 Savepic_Admin"""

    __slots__ = ()

    def __repr__(self) -> str:
        return "Savepic_Admin()"

    async def __call__(self, bot: Bot, event: Event) -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:
            return False
        return (
            f"{bot.adapter.get_name().split(maxsplit=1)[0].lower()}:{user_id}"
            in plugin_config.savepic_admin
            or user_id in plugin_config.savepic_admin  # 兼容旧配置
        )


PIC_AMDIN = Permission(Savepic_Admin())

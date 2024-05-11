""" 
This module is used to define the permission of the bot.
"""

from nonebot import get_plugin_config
from nonebot.adapters import Bot, Event
from nonebot.internal.permission import Permission
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11G
from .config import Config
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN


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


class BlackGroup(Permission):

    __slots__ = ()

    def __repr__(self) -> str:
        return "BlackGroup()"

    async def __call__(self, bot: Bot, event: Event) -> bool:
        if not isinstance(event, V11G):
            return True
        try:
            group_id = str(event.group_id)
        except Exception:
            return True
        return group_id not in plugin_config.black_group


PIC_AMDIN = Permission(Savepic_Admin())
BLACK_GROUP = Permission(BlackGroup())

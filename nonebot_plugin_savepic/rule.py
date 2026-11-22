"""
This module is used to define the permission of the bot.
"""

from nonebot.adapters import Bot, Event
from nonebot.internal.permission import Permission

from .config import plugin_config
from .adapter import get_platform


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
        name = bot.adapter.get_name().split(maxsplit=1)[0].lower()
        return (
            f"{get_platform(bot)}:{user_id}" in plugin_config.savepic_admin
            # Milky 统一记为 onebot，但写 milky:<QQ号> 也认
            or f"{name}:{user_id}" in plugin_config.savepic_admin
            or user_id in plugin_config.savepic_admin  # 兼容旧配置
        )


PIC_ADMIN = Permission(Savepic_Admin())

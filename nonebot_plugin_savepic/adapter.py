"""
适配器兼容层。

OneBot V11 与 Milky 之间的差异都收在这里，两个适配器都是可选导入，
只装其中一个也能正常加载插件。
"""

from typing import Optional, Union
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from nonebot import logger
from nonebot.adapters import Bot, Event, Message, MessageSegment
from nonebot.permission import Permission

try:
    from nonebot.adapters.onebot.v11 import Bot as V11Bot
    from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
    from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN as V11_GROUP_ADMIN
except ImportError:  # pragma: no cover
    V11Bot = V11GME = V11_GROUP_ADMIN = None  # type: ignore

try:
    from nonebot.adapters.milky import Bot as MilkyBot
    from nonebot.adapters.milky.event import GroupMessageEvent as MilkyGME
    from nonebot.adapters.milky.permission import GROUP_ADMIN as MILKY_GROUP_ADMIN
except ImportError:  # pragma: no cover
    MilkyBot = MilkyGME = MILKY_GROUP_ADMIN = None  # type: ignore

_GROUP_EVENTS: tuple[type[Event], ...] = tuple(e for e in (V11GME, MilkyGME) if e)
if not _GROUP_EVENTS:  # pragma: no cover
    raise ImportError("需要安装 nonebot-adapter-onebot 或 nonebot-adapter-milky")

GroupMessageEvent = Union[_GROUP_EVENTS]  # type: ignore
""" 任意受支持适配器的群消息事件，用于处理函数的参数注解 """

GROUP_ADMIN = Permission(
    *(c for p in (V11_GROUP_ADMIN, MILKY_GROUP_ADMIN) if p for c in p.checkers)
)
""" 群管理员，各适配器的检查器只对自己的事件生效 """


def is_milky(bot: Bot) -> bool:
    return MilkyBot is not None and isinstance(bot, MilkyBot)


def get_group_id(event: Event) -> Optional[int]:
    """群号，非群消息返回 None"""
    if V11GME is not None and isinstance(event, V11GME):
        return event.group_id
    if MilkyGME is not None and isinstance(event, MilkyGME):
        # Milky 的群号放在 peer_id
        return event.data.peer_id
    return None


def get_scope(event: Event) -> str:
    """作用域，群聊为 qq_group:<群号>，否则为 globe

    Milky 与 OneBot 用的是同一套 QQ 群号，所以沿用同样的格式，旧图片可以继续访问。
    """
    group_id = get_group_id(event)
    return "globe" if group_id is None else f"qq_group:{group_id}"


def get_platform(bot: Bot) -> str:
    """用户 ID 的前缀

    Milky 与 OneBot 都是 QQ 号，统一记为 onebot，
    这样已有的上传者记录和 savepic_admin 配置在迁移后依旧有效。
    """
    name = bot.adapter.get_name().split(maxsplit=1)[0].lower()
    return "onebot" if name == "milky" else name


def get_user_key(bot: Bot, event: Event) -> str:
    return f"{get_platform(bot)}:{event.get_user_id()}"


def get_reply_id(event: Event) -> Optional[str]:
    """被引用消息的 ID，OneBot 为 message_id，Milky 为 message_seq"""
    reply = getattr(event, "reply", None)
    if not reply:
        return None
    if hasattr(reply, "message_id"):
        return str(reply.message_id)
    return str(reply.message_seq)


def pick_picture(
    message: Message, event: Event, mface: bool = True
) -> Optional[MessageSegment]:
    """依次从消息、引用消息的图片、引用消息的商城表情中取出第一张图"""
    if picture := message.get("image"):
        return picture[0]
    reply = getattr(event, "reply", None)
    if not reply:
        return None
    if picture := reply.message.get("image"):
        return picture[0]
    if mface:
        # OneBot 为 mface，Milky 为 market_face
        for t in ("mface", "market_face"):
            if picture := reply.message.get(t):
                return picture[0]
    return None


async def picture_url(bot: Bot, picture: MessageSegment) -> str:
    """取得图片段可下载的 URL"""
    data = picture.data
    if is_milky(bot):
        if url := data.get("temp_url"):
            return url
        if resource_id := data.get("resource_id"):
            return await bot.get_resource_temp_url(resource_id=resource_id)  # type: ignore
        # 商城表情只有 url
        return data.get("url") or data.get("uri", "")
    return await rkey(bot, data["url"] if "url" in data else data["file"])


RKEY: dict[str, tuple[datetime, str]] = {
    "group": (datetime.min, ""),
    "private": (datetime.min, ""),
}


async def rkey(bot: Bot, url: str) -> str:
    """给 OneBot 的 NT 图片链接补上 rkey，其他情况原样返回"""
    if V11Bot is None or not isinstance(bot, V11Bot):
        return url
    if not url.startswith(
        (
            "https://multimedia.nt.qq.com.cn",
            "http://multimedia.nt.qq.com.cn",
        )
    ):
        return url
    if RKEY.get("group", (datetime.min, ""))[0] < datetime.now():
        ret = await bot.call_api("get_rkey")
        if isinstance(ret, dict):
            ret = ret.get("rkeys", [])
        elif isinstance(ret, list):
            pass
        else:
            logger.warning(f"get_rkey 返回了奇怪的东西: {ret}")
            ret = []
        for item in ret:
            RKEY[item.get("type")] = (
                datetime.fromtimestamp(int(item.get("created_at", 0)))
                + timedelta(seconds=int(item.get("ttl", 0)) - 300),
                item.get("rkey", "")[6:],
            )
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["rkey"] = [RKEY.get("group", (None, ""))[1]]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

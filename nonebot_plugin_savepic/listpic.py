from nonebot import on_command
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from arclet.alconna import Alconna, Args, Option, CommandMeta, Arparma
from nonebot.params import CommandArg
from nonebot_plugin_alconna import on_alconna
from nonebot.internal.adapter import Bot
from nonebot.adapters.onebot.v11 import GROUP_ADMIN
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg

from .rule import PIC_ADMIN
from .mvpic import INVALID_FILENAME_CHARACTERS
from .config import plugin_config
from .core.sql import listpic, delete, check_uploader

rmpic = on_alconna(
    Alconna(
        "rmpic",
        Option("-g", help_text="是否为全局图片，需要权限。"),
        Args["filename", str],
        meta=CommandMeta(
            description="删除已保存的图片。管理员和上传者可删除群内图片。"
        ),
    ),
    priority=5,
    block=True,
    use_cmd_start=True,
)
s_listpic = on_command("listpic", priority=5)
RKEY: dict[str, tuple[datetime, str]] = {
    "group": (datetime.min, ""),
    "private": (datetime.min, ""),
}


async def rkey(bot: Bot, url: str) -> str:
    if not url.startswith(
        (
            "https://multimedia.nt.qq.com.cn",
            "http://multimedia.nt.qq.com.cn",
        )
    ):
        return url
    if RKEY.get("group", (datetime.min, ""))[0] < datetime.now():
        for item in (await bot.call_api("get_rkey")).get("rkeys", []):
            RKEY[item.get("type")] = (
                datetime.fromtimestamp(item.get("created_at", 0))
                + timedelta(seconds=item.get("ttl", 0) - 300),
                item.get("rkey", "")[6:],
            )
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["rkey"] = [RKEY.get("group", (None, ""))[1]]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


@s_listpic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip().rsplit("\\page", maxsplit=1)
    try:
        if len(reg) > 1:
            reg, pages = reg
        else:
            reg, pages = reg[0], 1
        pages = int(pages)
    except Exception as ex:
        await s_listpic.finish(f"出错了。{ex}")

    group_id = "globe"
    if isinstance(event, V11GME):
        group_id = f"qq_group:{event.group_id}"

    try:
        pics = await listpic(reg, group_id, pages=pages)
        if not pics:
            return
        pics = [pic[0] + ("" if pic[1] else " ⭐") for pic in pics]

        cpp = max(plugin_config.count_per_page_in_list, 1)
        if plugin_config.forward_when_listpic:
            message = []
            for i in range(len(pics) // cpp + 1):
                if pics[i * cpp : (i + 1) * cpp]:
                    message.append(
                        {
                            "type": "node",
                            "data": {
                                "uin": str(event.get_user_id()),
                                "name": f"Page {pages+i}",
                                "content": V11Seg.text(
                                    "\n".join(pics[i * cpp : (i + 1) * cpp])
                                    + f"\n\nPage {pages+i}"
                                ),
                            },
                        },
                    )

            if isinstance(event, V11GME):
                await bot.call_api(
                    "send_group_forward_msg",
                    group_id=event.group_id,
                    messages=message,
                )
            else:
                await s_listpic.send(
                    V11Seg.forward(
                        await bot.call_api("send_forward_msg", messages=message)
                    )
                )
            return

        await s_listpic.send("\n".join(pics[:cpp]))
    except Exception as ex:
        await s_listpic.finish(f"出错了。{ex}")


@rmpic.handle()
async def _(bot: Bot, event: V11GME, command: Arparma):
    filename = command.filename
    if not isinstance(filename, str):
        await rmpic.finish("文件名无效")
    for c in INVALID_FILENAME_CHARACTERS:
        filename = filename.replace(c, "-")
    if not filename.endswith((".jpg", ".png", ".gif")):
        filename += ".jpg"

    user = (
        f"{bot.adapter.get_name().split(maxsplit=1)[0].lower()}:{event.get_user_id()}"
    )

    if not (
        await PIC_ADMIN(bot, event)
        or await GROUP_ADMIN(bot, event)
        or await check_uploader(
            filename,
            f"qq_group:{event.group_id}",
            user,
        )
    ):
        await rmpic.finish("没有权限")

    scope = f"qq_group:{event.group_id}"
    # 如果有 -g 选项
    if command.g:
        if not await PIC_ADMIN(bot, event):
            await rmpic.send("你的 -g 选项没有用哟")
        else:
            scope = "globe"
    try:
        await delete(filename, scope)
    except Exception as ex:
        await rmpic.finish(str(ex))
    await rmpic.finish("删除成功")

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from sqlalchemy.exc import DBAPIError

from .core.sql import listpic
from .config import plugin_config

UPLOADER: dict[str, str] = {}
s_listpic = on_command("listpic", priority=5)


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

    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
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

    except DBAPIError as ex:
        await s_listpic.finish(f"出错了。{ex.orig}")
    except Exception as ex:
        await s_listpic.finish(f"出错了。{ex}")

import random
from nonebot import on_command
from nonebot import get_plugin_config
from nonebot.params import CommandArg
from nonebot.internal.adapter import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from sqlalchemy.exc import DBAPIError

from .rule import BLACK_GROUP
from .config import WORDS
from .pic_sql import listpic
from .config import Config

p_config: Config = get_plugin_config(Config)
s_listpic = on_command("listpic", priority=5, permission=BLACK_GROUP)


@s_listpic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip().rsplit("\\page", maxsplit=1)
    try:
        if len(reg) > 1:
            reg, pages = reg
        else:
            reg, pages = reg[0], 0
        pages = int(pages)
    except Exception as ex:
        await s_listpic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}'
        )

    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        pics = await listpic(reg, group_id, pages=pages)
        if pics:
            message = {}
            cpp = p_config.count_per_page_in_list
            for i in range(len(pics) // cpp):
                message.append(
                    {
                        "type": "node",
                        "data": {
                            "uin": str(event.get_user_id()),
                            "name": f"Page {pages+i}",
                            "content": "\n".join(pics[i * cpp : (i + 1) * cpp])
                            + f"\n\nPage {pages+i}",
                        },
                    },
                )

            if isinstance(event, V11GME):
                await bot.call_api(
                    "send_group_forward_msg", group_id=event.group_id, messages=message
                )
            else:
                await s_listpic.finish(
                    V11Seg.forward(
                        await bot.call_api("send_forward_msg", messages=message)
                    )
                )

    except DBAPIError as ex:
        await s_listpic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex.orig}'
        )
    except Exception as ex:
        await s_listpic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}'
        )

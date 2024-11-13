from sqlalchemy.exc import DBAPIError
from nonebot import on_command
from nonebot.plugin import on_endswith
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg

from .core.sql import select_pic
from .core.fileio import load_pic
from .core.sql import countpic

cpic = on_command("countpic", priority=5)


@cpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        await bot.send(event, f"共查找到 {await countpic(reg, group_id)} 张图片。")
    except DBAPIError as ex:
        await cpic.finish(f"出错了喵~\n\n{ex.orig}")
    except Exception as ex:
        await cpic.finish(f"出错了喵~\n\n{ex}")


pic_listen = on_endswith((".jpg", ".png", ".gif"), priority=50, block=False)


@pic_listen.handle()
async def _(bot: Bot, event: Event):
    name = event.get_plaintext().strip()
    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        pic = await select_pic(name, group_id)
        if pic:
            file_ = await load_pic(pic.url)
            await bot.send(event, V11Seg.image(file=file_))
    except Exception as ex:
        await pic_listen.finish(str(ex))

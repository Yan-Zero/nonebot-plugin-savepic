import traceback
from pathlib import Path
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME

from .ai_utils import word2vec
from .rule import BLACK_GROUP
from .pic_sql import randpic

rpic = on_command("randpic", priority=5, permission=BLACK_GROUP)


def url_to_image(url: str):
    if url.startswith("http"):
        return V11Seg.image(url)
    return V11Seg.image(Path(url))


@rpic.handle()
async def _(bot, event, args: V11Msg = CommandArg()):
    name = args.extract_plain_text().strip()
    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        pic, t = await randpic(name, group_id, True)
        if not pic:
            await rpic.send("404 Not Found.")
            return
        await bot.send(
            event,
            V11Msg(
                [
                    pic.name,
                    "\n" + t if t else "",
                    url_to_image(pic.url),
                ]
            ),
        )
    except Exception as ex:
        with open("error.txt", "w+") as f:
            f.write("\n")
            traceback.print_exc(file=f)
        await rpic.finish(str(ex))

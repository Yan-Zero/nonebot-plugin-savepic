import traceback

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg

from .command import url_to_image
from .core.sql import cipdnar

cipr = on_command("cipdnar", priority=5)


@cipr.handle()
async def _(bot: Bot, event: Event, args: V11Msg = CommandArg()):
    name = args.extract_plain_text().strip()
    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        pic, t = await cipdnar(name, group_id)
        if not pic:
            await cipr.send("404 Not Found.")
            return
        await cipr.send(
            V11Msg(
                [
                    V11Seg.text(pic.name + ("\n" + t if t else "")),
                    await url_to_image(pic.url),
                ]
            )
        )
    except Exception as ex:
        with open("error.txt", "w+") as f:
            f.write("\n")
            traceback.print_exc(file=f)
        await cipr.finish(str(ex))

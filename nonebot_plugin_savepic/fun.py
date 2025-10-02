import traceback

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Event
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg

from .listpic import rkey
from .command import url_to_image
from .core.sql import cipdnar, simpic
from .core.utils import img2vec

cipr = on_command("cipdnar", priority=5)
cips = on_command("cipmis", priority=5)


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


@cips.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    picture = args.get("image")
    if not picture and hasattr(event, "reply"):
        picture = event.reply.message.get("image") if event.reply else None  # type: ignore
        if not picture:
            picture = event.reply.message.get("mface") if event.reply else None  # type: ignore
    if not picture:
        await cips.finish("请发送图片后再使用该指令喵~")
    try:
        vec = await img2vec(
            await rkey(bot, picture[0].data["url"]),
            title=args.extract_plain_text().strip(),
        )
        if vec is None:
            await cips.finish("图片特征提取失败喵~")
        group_id = (
            "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
        )
        sim, pic = await simpic(vec, group_id, sort_asc=True)
    except Exception as ex:
        await cips.finish(str(ex))

    if pic:
        ret = []
        if event.reply:  # type: ignore
            ret.append(V11Seg.reply(event.reply.message_id))  # type: ignore
        ret.append(f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)")
        ret.append(await url_to_image(pic.url))
        await cips.send(V11Msg(ret))
    else:
        await cips.send("没有找到不相似的图片喵~")

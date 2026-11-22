import traceback

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Event
from nonebot.adapters import Message
from nonebot_plugin_alconna import UniMessage, Text, Reply

from .adapter import get_scope, get_reply_id, pick_picture, picture_url
from .command import url_to_image
from .core.sql import cipdnar, simpic
from .core.utils import img2vec

cipr = on_command("cipdnar", priority=5)
cips = on_command("cipmis", priority=5)


@cipr.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    name = args.extract_plain_text().strip()
    group_id = get_scope(event)
    try:
        pic, t = await cipdnar(name, group_id)
        if not pic:
            await cipr.send("404 Not Found.")
            return
        await UniMessage(
            [
                Text(pic.name + ("\n" + t if t else "")),
                await url_to_image(pic.url),
            ]
        ).send()
    except Exception as ex:
        with open("error.txt", "w+") as f:
            f.write("\n")
            traceback.print_exc(file=f)
        await cipr.finish(str(ex))


@cips.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    picture = pick_picture(args, event)
    if picture is None:
        await cips.finish("请发送图片后再使用该指令喵~")
    try:
        vec = await img2vec(
            await picture_url(bot, picture),
            title=args.extract_plain_text().strip(),
        )
        if vec is None:
            await cips.finish("图片特征提取失败喵~")
        group_id = get_scope(event)
        sim, pic = await simpic(vec, group_id, sort_asc=True)
    except Exception as ex:
        await cips.finish(str(ex))

    if pic:
        ret = UniMessage()
        if reply_id := get_reply_id(event):
            ret.append(Reply(reply_id))
        ret.append(Text(f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)"))
        ret.append(await url_to_image(pic.url))
        await ret.send()
    else:
        await cips.send("没有找到不相似的图片喵~")

from sqlalchemy.exc import DBAPIError
from nonebot import on_command
from nonebot.plugin import on_endswith
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Message
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg

from .config import p_config
from .core.sql import simpic
from .core.sql import countpic
from .core.sql import select_pic
from .core.utils import img2vec
from .core.fileio import load_pic

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


s_simpic = on_command("simpic", priority=5)


@s_simpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    if p_config.simpic_model not in ["ViT/16"]:
        await s_simpic.finish("当前配置的模型不支持相似图片搜索喵~")
    try:
        picture = args.get("image")
        if not picture:
            picture = event.reply.message.get("image") if event.reply else None
        if not picture:
            await s_simpic.finish("请发送图片后再使用该指令喵~")
        vec = img2vec(await load_pic(picture[0].data["url"]))
        ignore_min = False
        if args.extract_plain_text().strip() == "-i":
            ignore_min = True
        group_id = (
            "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
        )
        sim, pic = await simpic(vec, group_id, ignore_min)
        if pic:
            await bot.send(
                event,
                Message(
                    [
                        V11Seg.reply(event.reply.message_id),
                        f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)\n",
                        await load_pic(pic.url),
                    ]
                ),
            )
        else:
            await s_simpic.send("没有找到相似的图片喵~")
    except Exception as ex:
        await s_simpic.finish(str(ex))

import traceback

from pathlib import Path
from nonebot import on_command
from arclet.alconna import Alconna, Args, Option, CommandMeta, Arparma
from nonebot.plugin import on_endswith
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Message
from nonebot.adapters import Event
from nonebot_plugin_alconna import on_alconna
from nonebot.adapters.onebot.v11 import GROUP_ADMIN
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.message import Message as V11Msg

from .rule import PIC_ADMIN
from .mvpic import INVALID_FILENAME_CHARACTERS
from .core.sql import simpic, delete, randpic, countpic, select_pic, check_uploader
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
        if url := await select_pic(name, group_id):
            file_ = await load_pic(url)
            await pic_listen.send(V11Seg.image(file=file_))
    except Exception as ex:
        await pic_listen.finish(str(ex))


rpic = on_command("randpic", priority=5)


def url_to_image(url: str):
    if url.startswith("http"):
        return V11Seg.image(url)
    return V11Seg.image(Path(url))


@rpic.handle()
async def _(bot: Bot, event: Event, args: V11Msg = CommandArg()):
    name = args.extract_plain_text().strip()
    group_id = (
        "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
    )
    try:
        pic, t = await randpic(name, group_id, True)
        if not pic:
            await rpic.send("404 Not Found.")
            return
        await rpic.send(
            V11Msg(
                [
                    V11Seg.text(pic.name + "\n" + t if t else ""),
                    url_to_image(pic.url),
                ]
            )
        )
    except Exception as ex:
        with open("error.txt", "w+") as f:
            f.write("\n")
            traceback.print_exc(file=f)
        await rpic.finish(str(ex))


s_simpic = on_command("simpic", priority=5)


@s_simpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    try:
        picture = args.get("image")
        if not picture and hasattr(event, "reply"):
            picture = event.reply.message.get("image") if event.reply else None  # type: ignore
        if not picture:
            await s_simpic.finish("请发送图片后再使用该指令喵~")

        vec = await img2vec(picture[0].data["url"])
        if vec is None:
            await s_simpic.finish("图片特征提取失败喵~")
        group_id = (
            "globe" if not isinstance(event, V11GME) else f"qq_group:{event.group_id}"
        )
        sim, pic = await simpic(vec, group_id, True)
    except Exception as ex:
        await s_simpic.finish(str(ex))

    if pic:
        ret = []
        if event.reply:  # type: ignore
            ret.append(V11Seg.reply(event.reply.message_id))  # type: ignore
        ret.append(f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)")
        ret.append(url_to_image(pic.url))
        await s_simpic.send(V11Msg(ret))
    else:
        await s_simpic.send("没有找到相似的图片喵~")


# delpic = on_command("delpic", priority=5)
rmpic = on_alconna(
    Alconna(
        "/rmpic",
        Option("-g", help_text="是否为全局图片，需要权限。"),
        Args.filename[str],  # type: ignore
        meta=CommandMeta(
            description="删除已保存的图片。管理员和上传者可删除群内图片。"
        ),
    ),
    priority=5,
    block=True,
)


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

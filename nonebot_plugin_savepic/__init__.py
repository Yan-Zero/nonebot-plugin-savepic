from nonebot import require
from nonebot import get_driver
from nonebot import on_command
from nonebot.params import CommandArg, Arg
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.internal.adapter.bot import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State
from nonebot.plugin import PluginMetadata
from asyncpg.exceptions import InvalidRegularExpressionError
from arclet.alconna import Alconna, Option, Args, CommandMeta, append
import os

require("nonebot_plugin_datastore")

from .config import Config
from .pic_sql import savepic, rename, delete, write_pic, randpic, load_pic, select_pic
from .rule import PIC_AMDIN
from .ext_listener import pic_listen
from .picture import p_hash


__plugin_meta__ = PluginMetadata(
    name="Savepic",
    description="表情包保存",
    usage="""用法:
/savepic <文件名> <图片>
/savepic -g <文件名> <全局图片>
/savepic -d <文件名> 删除图图片
/savepic -m <原文件名> <新文件名> 重命名图片
/randpic <关键词> 随机图片
<文件名> 发送图片""",
    config=Config,
    homepage="https://github.com/Yan-Zero/nonebot-plugin-savepic",
    type="application",
    supported_adapters=["~onebot.v11"],
)

INVALID_FILENAME_CHARACTERS = r'\/:*?"<>|'

p_config = Config.parse_obj(get_driver().config)

rpic = on_command("randpic", aliases={"随机图"}, priority=5)


@rpic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = (
        "globe"
        if not isinstance(event, GroupMessageEvent)
        else f"qq_group:{event.group_id}"
    )
    try:
        pic = await randpic(reg, group_id)
        if pic:
            file_ = await load_pic(pic.url)
            await bot.send(event, V11Msg([pic.name + "\n", V11Seg.image(file=file_)]))
    except InvalidRegularExpressionError:
        await rpic.finish("正则表达式错误")
    except Exception as ex:
        await rpic.finish(str(ex))


spic = on_command("savepic", aliases={"存图"}, priority=5)
a_spic = Alconna(
    "/savepic",
    Option("-d", help_text="删除图片"),
    Option("-g", help_text="全局"),
    Option("-ac", help_text="允许相似碰撞"),
    Args.filename[str],
    meta=CommandMeta(description="保存图片，默认保存到本群"),
)


@spic.handle()
async def _(
    bot: Bot,
    matcher: Matcher,
    event: GroupMessageEvent,
    state: T_State,
):
    command = a_spic.parse(event.message.extract_plain_text())
    if not command.matched:
        await spic.finish(str(command.error_info) + "\n\n" + a_spic.get_help())

    state["savepiv_group"] = "globe" if command.g else f"qq_group:{event.group_id}"
    filename = command.filename
    for c in INVALID_FILENAME_CHARACTERS:
        filename = filename.replace(c, "-")
    if not filename.endswith((".jpg", ".png", ".gif")):
        filename += ".jpg"
    state["savepiv_filename"] = filename
    state["savepiv_ac"] = command.ac is not None

    if command.d:
        if not await PIC_AMDIN(bot, event):
            await spic.finish("不支持选项 -d")
        try:
            await delete(filename, state["savepiv_group"])
        except Exception as ex:
            await spic.finish(str(ex))
        await spic.finish("图片已删除")

    pic = await select_pic(filename, state["savepiv_group"])
    if pic and pic.group == state["savepiv_group"]:
        spic.finish("文件名已存在。")

    picture = event.message.get("image")
    if not picture and event.reply:
        picture = event.reply.message.get("image")
    if picture:
        matcher.set_arg("picture", picture)


@spic.got("picture", "图呢？")
async def _(state: T_State, picture: V11Msg = Arg()):
    picture = picture.get("image")
    if not picture:
        await spic.finish("6，这也不是图啊")

    try:
        dir = await write_pic(picture[0].data["url"], p_config.savepic_dir)
    except Exception as ex:
        await spic.finish("存图失败。" + "\n" + str(ex))
    try:
        await savepic(
            state["savepiv_filename"],
            dir,
            p_hash(await load_pic(dir)),
            state["savepiv_group"],
            state["savepiv_ac"],
        )
        await spic.send("保存成功")
    except Exception as ex:
        os.remove(dir)
        await spic.finish(str(ex))


s_mvpic = on_command("mvpic", priority=5)
a_mvpic = Alconna(
    "/mvpic",
    Option("-l", args=Args.filename[str], help_text="本地图片", action=append),
    Option("-g", args=Args.filename[str], help_text="全局图片", action=append),
    meta=CommandMeta(description="重命名图片，按照参数先后判断"),
)


@s_mvpic.handle()
async def _(
    bot: Bot,
    event: GroupMessageEvent,
):
    if not await PIC_AMDIN(bot, event):
        await spic.finish("不支持选项 -m")

    cmd = a_mvpic.parse(event.message.extract_plain_text())
    if not cmd.matched:
        await s_mvpic.finish(str(cmd.error_info) + "\n\n" + a_mvpic.get_help())
    options = cmd.options
    if not options:
        await s_mvpic.finish("文件名呢？" + "\n\n" + a_mvpic.get_help())

    sg = "globe" if list(options.keys())[0] == "g" else f"qq_group:{event.group_id}"
    if len(options["g" if sg == "globe" else "l"].args.get("filename", [])) >= 2:
        dg = sg
    else:
        dg = "globe" if sg != "globe" else f"qq_group:{event.group_id}"
    if ("g" if dg == "globe" else "l") not in options:
        await s_mvpic.finish("至多只有一个文件名哦？" + "\n\n" + a_mvpic.get_help())

    sname = options["g" if sg == "globe" else "l"].args["filename"][0]
    dname = options["g" if dg == "globe" else "l"].args["filename"][
        1 if sg == dg else 0
    ]
    for c in INVALID_FILENAME_CHARACTERS:
        sname = sname.replace(c, "-")
        dname = dname.replace(c, "-")
    if not sname.endswith((".jpg", ".png", ".gif")):
        sname += ".jpg"
    if not dname.endswith((".jpg", ".png", ".gif")):
        dname += ".jpg"

    try:
        await rename(sname, dname, sg, dg)
    except Exception as ex:
        await spic.finish(str(ex))
    await spic.finish("图片已重命名")

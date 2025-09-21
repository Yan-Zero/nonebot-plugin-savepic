from nonebot import on_command
from nonebot.params import CommandArg, Arg
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.typing import T_State
from arclet.alconna import Alconna, Args, Option, CommandMeta, Arparma
from nonebot_plugin_alconna import on_alconna
from nonebot.internal.adapter import Bot

from .rule import PIC_ADMIN
from .mvpic import INVALID_FILENAME_CHARACTERS
from .config import Config
from .listpic import plugin_config
from .command import url_to_image
from .core.sql import savepic, regexp_pic
from .core.utils import img2vec
from .core.error import SameNameException
from .core.error import SimilarPictureException
from .core.fileio import write_pic, load_pic, del_pic


__plugin_meta__ = PluginMetadata(
    name="Savepic",
    description="表情包保存",
    usage="""用法:
/savepic <文件名> <图片>
/savepic -g <文件名> <全局图片>
/savepic -d <文件名> 删除图图片
/randpic <关键词> 随机图片
<文件名> 发送图片""",
    config=Config,
    homepage="https://github.com/Yan-Zero/nonebot-plugin-savepic",
    type="application",
    supported_adapters=set(["~onebot.v11"]),
)

repic = on_command("repic", priority=5)
spic = on_alconna(
    Alconna(
        "/savepic",
        Option("-g", help_text="全局"),
        Option("-ac", help_text="允许相似碰撞"),
        Args.filename[str],  # type: ignore
        meta=CommandMeta(description="保存图片，默认保存到本群"),
    )
)


@repic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = (
        "globe"
        if not isinstance(event, GroupMessageEvent)
        else f"qq_group:{event.group_id}"
    )
    try:
        if pic := await regexp_pic(reg, group_id):
            await bot.send(
                event, V11Msg([V11Seg.text(pic.name), url_to_image(pic.url)])
            )
    except Exception as ex:
        await repic.finish(f"出错了。{ex}")


@spic.handle()
async def _(
    bot: Bot,
    matcher: Matcher,
    event: GroupMessageEvent,
    state: T_State,
    command: Arparma,
):
    if not command.matched:
        await spic.finish(str(command.error_info))

    filename = command.filename
    if not isinstance(filename, str):
        await spic.finish("文件名无效")
    for c in INVALID_FILENAME_CHARACTERS:
        filename = filename.replace(c, "-")
    if not filename.endswith((".jpg", ".png", ".gif")):
        filename += ".jpg"

    state["savepiv_group"] = (
        "globe"
        if command.g and await PIC_ADMIN(bot, event)
        else f"qq_group:{event.group_id}"
    )

    if command.g and not await PIC_ADMIN(bot, event):
        await spic.send("你的 -g 选项没有用哟")

    state["savepiv_filename"] = filename
    state["savepiv_ac"] = command.ac is not None

    picture = event.message.get("image")
    if not picture and event.reply:
        picture = event.reply.message.get("image")
    if picture:
        matcher.set_arg("picture", picture)


@spic.got("picture", "图呢？")
async def _(bot: Bot, state: T_State, event, picture: V11Msg = Arg()):
    picture = picture.get("image")
    if not picture:
        await spic.finish("6，这也不是图啊")

    try:
        dir = await write_pic(picture[0].data["url"], plugin_config.savepic_dir)
    except Exception as ex:
        await spic.finish("存图失败。" + "\n" + str(ex))

    try:
        r = await savepic(
            filename=state["savepiv_filename"],
            url=dir,
            scope=state["savepiv_group"],
            uploader=f"{bot.adapter.get_name().split(maxsplit=1)[0].lower()}:{event.get_user_id()}",
            vec=await img2vec(picture[0].data["url"], state["savepiv_filename"]),
            collision_allow=state["savepiv_ac"],
        )
    except SameNameException:
        await del_pic(dir)
        await spic.finish("文件名重复")
    except SimilarPictureException as ex:
        await del_pic(dir)
        try:
            image = await load_pic(ex.url)
        except Exception as exc:
            await spic.finish(f"出错了。{exc}")
        await spic.finish(
            V11Msg(
                [
                    V11Seg.text(
                        "存在相似图片"
                        + "\n\n"
                        + ex.name
                        + f"\n(相似度：{'%.4g' % (min(ex.similarity * 100, 100.0))}%)\n"
                    ),
                    V11Seg.image(file=image),
                ]
            )
        )
    except Exception as ex:
        await del_pic(dir)
        await spic.finish(f"出错了。{ex}")
    if r:
        await spic.send(f"保存成功，但是名字为`{r}`")
    else:
        await spic.send("保存成功")

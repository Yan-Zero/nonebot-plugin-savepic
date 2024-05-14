from pathlib import Path
from nonebot import require
from nonebot import get_plugin_config
from nonebot import on_command
from nonebot.params import CommandArg, Arg
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.dependencies import Dependent
from sqlalchemy.exc import DBAPIError
from arclet.alconna import Alconna, Option, Args, CommandMeta
import os
import random
from typing import (
    Any,
    Union,
    Callable,
    Iterable,
    Optional,
)
from nonebot.typing import (
    T_State,
    T_Handler,
)
from nonebot.consts import ARG_KEY
from nonebot.internal.params import Depends
from nonebot.internal.adapter import (
    Bot,
    Event,
    Message,
    MessageSegment,
    MessageTemplate,
)


require("nonebot_plugin_datastore")

from .error import (
    SimilarPictureException,
    SameNameException,
)  # noqa: E402, E501
from .config import Config
from .config import WORDS
from .pic_sql import (  # noqa: E402
    savepic,
    delete,
    regexp_pic,
)
from .rule import PIC_AMDIN
from .rule import BLACK_GROUP
from .rule import GROUP_ADMIN
from .picture import write_pic, load_pic
from .ai_utils import img2vec
from .randpic import url_to_image
from .mvpic import INVALID_FILENAME_CHARACTERS
from .listpic import s_listpic
from .ext_listener import pic_listen
from .countpic import cpic


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
    supported_adapters=["~onebot.v11"],
)

p_config = get_plugin_config(Config)
repic = on_command("repic", priority=5, permission=BLACK_GROUP)
spic = on_command("savepic", priority=5, permission=BLACK_GROUP)
a_spic = Alconna(
    "/savepic",
    Option("-d", help_text="删除图片"),
    Option("-g", help_text="全局"),
    Option("-ac", help_text="允许相似碰撞"),
    Args.filename[str],
    meta=CommandMeta(description="保存图片，默认保存到本群"),
)
s_simpic = on_command("simpic", priority=5, permission=BLACK_GROUP)


def got_random_prompt(
    cls: Matcher,
    key: str,
    prompt: Optional[list[Union[str, Message, MessageSegment, MessageTemplate]]] = None,
    parameterless: Optional[Iterable[Any]] = None,
) -> Callable[[T_Handler], T_Handler]:
    """装饰一个函数来指示 NoneBot 获取一个参数 `key`

    当要获取的 `key` 不存在时接收用户新的一条消息再运行该函数，
    如果 `key` 已存在则直接继续运行

    参数:
        key: 参数名
        prompt: 在参数不存在时向用户发送的消息
        parameterless: 非参数类型依赖列表
    """

    async def _key_getter(event: Event, matcher: "Matcher"):
        matcher.set_target(ARG_KEY.format(key=key))
        if matcher.get_target() == ARG_KEY.format(key=key):
            matcher.set_arg(key, event.get_message())
            return
        if matcher.get_arg(key, ...) is not ...:
            return
        await matcher.reject("" if not prompt else random.choice(prompt))

    _parameterless = (Depends(_key_getter), *(parameterless or ()))

    def _decorator(func: T_Handler) -> T_Handler:
        if cls.handlers and cls.handlers[-1].call is func:
            func_handler = cls.handlers[-1]
            new_handler = Dependent(
                call=func_handler.call,
                params=func_handler.params,
                parameterless=Dependent.parse_parameterless(
                    tuple(_parameterless), cls.HANDLER_PARAM_TYPES
                )
                + func_handler.parameterless,
            )
            cls.handlers[-1] = new_handler
        else:
            cls.append_handler(func, parameterless=_parameterless)

        return func

    return _decorator


@repic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = (
        "globe"
        if not isinstance(event, GroupMessageEvent)
        else f"qq_group:{event.group_id}"
    )
    try:
        pic = await regexp_pic(reg, group_id)
        if pic:
            await bot.send(event, V11Msg([pic.name, url_to_image(pic.url)]))
    except DBAPIError as ex:
        await repic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex.orig}'
        )
    except Exception as ex:
        await repic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}'
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

    state["savepiv_group"] = (
        "globe"
        if command.g and await PIC_AMDIN(bot, event)
        else f"qq_group:{event.group_id}"
    )
    state["savepiv_warning"] = (
        ""
        if not command.g or await PIC_AMDIN(bot, event)
        else "\n\n你的 -g 选项没有用哟"
    )
    filename = command.filename
    for c in INVALID_FILENAME_CHARACTERS:
        filename = filename.replace(c, "-")
    if not filename.endswith((".jpg", ".png", ".gif")):
        filename += ".jpg"
    state["savepiv_filename"] = filename
    state["savepiv_ac"] = command.ac is not None

    if command.d:
        if not (await PIC_AMDIN(bot, event) or await GROUP_ADMIN(bot, event)):
            await spic.finish(
                random.choice(WORDS.get("permission denied", ["没有权限"]))
            )
        try:
            await delete(filename, state["savepiv_group"])
        except Exception as ex:
            await spic.finish(str(ex))
        await spic.finish("图片已删除" + state["savepiv_warning"])

    picture = event.message.get("image")
    if not picture and event.reply:
        picture = event.reply.message.get("image")
    if picture:
        matcher.set_arg("picture", picture)


@got_random_prompt(spic, "picture", WORDS.get("wait for image", ["图呢"]))
async def _(state: T_State, picture: V11Msg = Arg()):
    picture = picture.get("image")
    if not picture:
        await spic.finish(random.choice(WORDS.get("not image", ["6，这也不是图啊"])))

    try:
        dir = await write_pic(picture[0].data["url"], p_config.savepic_dir)
    except Exception as ex:
        await spic.finish("存图失败。" + "\n" + str(ex))
    try:
        await savepic(
            state["savepiv_filename"],
            dir,
            img2vec(await load_pic(dir), state["savepiv_filename"]),
            state["savepiv_group"],
            state["savepiv_ac"],
        )
    except SameNameException:
        os.remove(dir)
        await spic.finish(
            random.choice(WORDS.get("name has been taken", ["文件名重复"]))
        )
    except SimilarPictureException as ex:
        os.remove(dir)
        try:
            image = await load_pic(ex.url)
        except Exception as exc:
            await spic.finish(
                f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{exc}'
            )

        await spic.finish(
            V11Msg(
                [
                    random.choice(WORDS.get("similar picture", ["存在相似图片"])),
                    "\n\n" + ex.name,
                    f"\n(相似度：{'%.4g' % (min(ex.similarity * 100, 100.0))}%)\n",
                    V11Seg.image(file=image),
                ]
            )
        )
    except Exception as ex:
        os.remove(dir)
        await spic.finish(f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}')
    await spic.send(
        random.choice(WORDS.get("save succeed", ["保存成功"]))
        + state["savepiv_warning"]
    )


@s_simpic.handle()
async def _(bot: Bot, event: MessageEvent, args: V11Msg = CommandArg()):
    if True:
        await s_simpic.finish("simpic 并未开启喵。")

    picture = event.reply.message.get("image") if event.reply else None
    if not picture:
        await s_simpic.finish(
            random.choice(
                WORDS.get("missing image reference", ["没找到引用消息中的图片"])
            )
        )
    vec = img2vec(await load_pic(picture[0].data["url"]))
    ignore_diagonal = True
    ignore_min = False
    if args.extract_plain_text().strip() == "-n":
        ignore_diagonal = False
    elif args.extract_plain_text().strip() == "-i":
        ignore_min = True
    group_id = (
        "globe"
        if not isinstance(event, GroupMessageEvent)
        else f"qq_group:{event.group_id}"
    )
    try:
        sim, pic = await get_most_similar_pic(
            vec, group_id, ignore_diagonal, ignore_min
        )
        if pic:
            await bot.send(
                event,
                V11Msg(
                    [
                        V11Seg.reply(event.reply.message_id),
                        f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)\n",
                        url_to_image(pic.url),
                    ]
                ),
            )
        else:
            await s_simpic.send(random.choice(WORDS.get("not found", ["Nope."])))
    except Exception as ex:
        await s_simpic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}'
        )

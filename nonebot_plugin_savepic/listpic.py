from nonebot import on_command
from arclet.alconna import Alconna, Args, Option, CommandMeta, Arparma
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot_plugin_alconna import on_alconna, UniMessage, Reference, CustomNode
from nonebot.internal.adapter import Bot

from .rule import PIC_ADMIN
from .adapter import GROUP_ADMIN, GroupMessageEvent
from .adapter import get_scope, get_user_key
from .adapter import rkey, RKEY  # noqa: F401 兼容旧的导入路径
from .config import plugin_config
from .core.sql import listpic, delete, check_uploader

rmpic = on_alconna(
    Alconna(
        "rmpic",
        Option("-g", help_text="是否为全局图片，需要权限。"),
        Args["filename", str],
        meta=CommandMeta(
            description="删除已保存的图片。管理员和上传者可删除群内图片。"
        ),
    ),
    priority=5,
    block=True,
    use_cmd_start=True,
)
s_listpic = on_command("listpic", priority=5)


@s_listpic.handle()
async def _(bot: Bot, event, args: Message = CommandArg()):
    reg = args.extract_plain_text().strip().rsplit("\\page", maxsplit=1)
    try:
        if len(reg) > 1:
            reg, pages = reg
        else:
            reg, pages = reg[0], 1
        pages = int(pages)
    except Exception as ex:
        await s_listpic.finish(f"出错了。{ex}")

    group_id = get_scope(event)

    try:
        pics = await listpic(reg, group_id, pages=pages)
        if not pics:
            return
        pics = [pic[0] + ("" if pic[1] else " ⭐") for pic in pics]

        cpp = max(plugin_config.count_per_page_in_list, 1)
        if plugin_config.forward_when_listpic:
            nodes = []
            for i in range(len(pics) // cpp + 1):
                if pics[i * cpp : (i + 1) * cpp]:
                    nodes.append(
                        CustomNode(
                            uid=str(event.get_user_id()),
                            name=f"Page {pages+i}",
                            content="\n".join(pics[i * cpp : (i + 1) * cpp])
                            + f"\n\nPage {pages+i}",
                        )
                    )

            # 合并转发交给 uniseg，由它按适配器选择对应的发送方式
            await UniMessage(Reference(nodes=nodes)).send()
            return

        await s_listpic.send("\n".join(pics[:cpp]))
    except Exception as ex:
        await s_listpic.finish(f"出错了。{ex}")


@rmpic.handle()
async def _(bot: Bot, event: GroupMessageEvent, command: Arparma):
    filename = command.filename
    if not isinstance(filename, str):
        await rmpic.finish("文件名无效")
    # for c in INVALID_FILENAME_CHARACTERS:
    #     filename = filename.replace(c, "-")
    if not filename.endswith((".jpg", ".png", ".gif")):
        filename += ".jpg"

    user = get_user_key(bot, event)

    if not (
        await PIC_ADMIN(bot, event)
        or await GROUP_ADMIN(bot, event)
        or await check_uploader(
            filename,
            get_scope(event),
            user,
        )
    ):
        await rmpic.finish("没有权限")

    scope = get_scope(event)
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

import random
from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.internal.adapter import Bot
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from .rule import BLACK_GROUP
from .rule import PIC_AMDIN
from .rule import GROUP_ADMIN
from .config import WORDS
from .pic_sql import rename
from .error import NoPictureException
from .error import SameNameException

s_mvpic = on_command("mvpic", priority=5, permission=BLACK_GROUP)
INVALID_FILENAME_CHARACTERS = r'\/:*?"<>|'


# mvpic -l name -g name
# mvpic -lg name name
# mvpic -gl name name
# mvpic -l -g name
# mvpic -g -l name
# mvpic -gl name
# mvpic -lg name
# mvpic name name


@s_mvpic.handle()
async def _(bot: Bot, event: V11GME, args=CommandArg()):
    if not (await PIC_AMDIN(bot, event) or await GROUP_ADMIN(bot, event)):
        await s_mvpic.finish(
            random.choice(WORDS.get("permission denied", ["没有权限"]))
        )

    cmd = args.extract_plain_text().strip()
    name = []
    options = []

    def parser():
        pos = 0
        nonlocal cmd, name, options

        def _str(t: str) -> str:
            nonlocal pos, cmd

            result = ""
            pos += 1
            while pos < len(cmd):
                if cmd[pos] == t:
                    break
                if not t and not cmd[pos].strip():
                    break

                if cmd[pos] == "\\":
                    pos += 1
                    if pos >= len(cmd):
                        result += "\\"
                        break
                    elif cmd[pos] == "'":
                        result += "'"
                    elif cmd[pos] == '"':
                        result += '"'
                    elif cmd[pos] == "t":
                        result += "\t"
                    elif cmd[pos] == "n":
                        result += "\n"
                    elif cmd[pos] == "r":
                        result += "\r"
                    elif cmd[pos] == "\\":
                        result += "\\"
                    else:
                        result += "\\"
                        pos -= 1
                else:
                    result += cmd[pos]
                pos += 1
            pos += 1
            return result

        def _options() -> list[str]:
            nonlocal pos, cmd

            pos += 1
            result = []
            while pos < len(cmd) and cmd[pos].strip():
                result.append(cmd[pos])
                pos += 1
            return result

        while pos < len(cmd):
            if cmd[pos] == "'":
                name.append(_str("'"))
            elif not cmd[pos].strip():
                pos += 1
            elif cmd[pos] == "-":
                options.extend(_options())
            elif cmd[pos] == '"':
                name.append(_str('"'))
            else:
                pos -= 1
                name.append(_str(""))

    parser()
    if not name:
        await s_mvpic.finish("文件名呢？")
    if not options:
        options = ["l"]

    if (not await PIC_AMDIN(bot, event)) and await GROUP_ADMIN(bot, event):
        if "g" in options:
            await s_mvpic.finish("管理员不能改全局名称哦~")

    sname = name[0]
    dname = name[1] if len(name) > 1 else sname
    for c in INVALID_FILENAME_CHARACTERS:
        sname = sname.replace(c, "-")
        dname = dname.replace(c, "-")
    if not sname.endswith((".jpg", ".png", ".gif")):
        sname += ".jpg"
    if not dname.endswith((".jpg", ".png", ".gif")):
        dname += ".jpg"

    sg = "globe" if options[0] == "g" else f"qq_group:{event.group_id}"
    dg = options[1] if len(options) > 1 else options[0]
    dg = "globe" if dg == "g" else f"qq_group:{event.group_id}"

    if sname == dname and sg == dg:
        await s_mvpic.finish("嗯，什么都没有变化嘛。")

    try:
        await rename(sname, dname, sg, dg)
    except NoPictureException as ex:
        await s_mvpic.finish(
            random.choice(WORDS.get("not found", [ex.name + " 没有找到哦"]))
            + f"\n{ex.name} 没有找到哦"
        )
    except SameNameException:
        await s_mvpic.finish(
            random.choice(WORDS.get("name has been taken", ["文件名重复"]))
        )
    except Exception as ex:
        await s_mvpic.finish(
            f'{random.choice(WORDS.get("error", ["出错了喵~"]))}\n\n{ex}'
        )
    await s_mvpic.finish(random.choice(WORDS.get("rename succeed", ["图片已重命名"])))

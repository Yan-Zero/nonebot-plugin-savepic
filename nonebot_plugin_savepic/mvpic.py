from nonebot import on_command, logger
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.utils import f2s
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN

from .rule import PIC_ADMIN
from .core.sql import rename, select_pic, check_uploader
from .core.utils import img2vec
from .core.fileio import load_pic
from .core.error import NoPictureException
from .core.error import SameNameException

INVALID_FILENAME_CHARACTERS = r'\/:*?"<>|'
s_mvpic = on_command("mvpic", priority=5)
update_vec = on_command("pic.vec.update", permission=SUPERUSER, priority=1, block=True)


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

    user = (
        f"{bot.adapter.get_name().split(maxsplit=1)[0].lower()}:{event.get_user_id()}"
    )

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

    if not (await PIC_ADMIN(bot, event)) and "g" in options:
        await s_mvpic.finish("不能改全局名称哦~\n尝试使用 -l 选项")

    if not (
        await PIC_ADMIN(bot, event)
        or await GROUP_ADMIN(bot, event)
        or await check_uploader(
            sname,
            sg,
            user,
        )
    ):
        await s_mvpic.finish("没有权限")

    if sname == dname and sg == dg:
        await s_mvpic.finish("嗯，什么都没有变化嘛。")

    v = None
    if sname != dname:
        url = await select_pic(sname, sg, True)
        if not url:
            await s_mvpic.finish(f"{sname} 没有找到哦")
        v = await img2vec(
            await bot.call_api("upload_image", file=f2s(await load_pic(url))), dname
        )

    try:
        await rename(sname, dname, sg, dg, is_admin=await PIC_ADMIN(bot, event), vec=v)
    except NoPictureException as ex:
        await s_mvpic.finish(f"{ex.name} 没有找到哦")
    except SameNameException:
        await s_mvpic.finish("文件名重复")
    except Exception as ex:
        await s_mvpic.finish(f"出错了。{ex}")
    await s_mvpic.finish("图片已重命名")


@update_vec.handle()
async def _(bot: Bot):
    from .core import sql

    if not sql.POOL:
        await update_vec.finish("数据库未初始化")
    await update_vec.send("开始更新图片特征向量...")
    async with sql.POOL.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM picdata WHERE vec IS NULL;")
        if count == 0:
            await update_vec.finish("没有需要更新的图片特征向量")
        finish = 0
        await update_vec.send(f"共有 {count} 张图片需要更新")
        async with conn.transaction():
            async for record in conn.cursor(
                "SELECT name, url FROM picdata WHERE vec IS NULL;"
            ):
                finish += 1
                # 每10%更新一次进度
                if finish % max(1, count // 10) == 0:
                    await update_vec.send(
                        f"已完成 {finish}/{count} 张图片的特征向量更新"
                    )
                try:
                    vec = await img2vec(
                        await bot.call_api(
                            "upload_image", file=f2s(await load_pic(record["url"]))
                        ),
                        record["name"],
                    )
                    if vec is None:
                        logger.warning(f"图片 {record['name']} 特征提取失败，跳过")
                        continue
                    await conn.execute(
                        "UPDATE picdata SET vec = $1 WHERE url = $2;",
                        str(vec.tolist()),
                        record["url"],
                    )
                except Exception as ex:
                    logger.error(
                        f"图片 {record['name']} 特征提取失败，跳过，错误信息：{ex}"
                    )
    await update_vec.finish("图片特征向量更新完成")

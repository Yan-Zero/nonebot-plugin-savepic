import traceback

from pathlib import Path
from nonebot import on_command
from nonebot.plugin import on_endswith
from nonebot.params import CommandArg
from nonebot.adapters import Bot
from nonebot.adapters import Message
from nonebot.adapters import Event
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import UniMessage, Image, Text, Reply

from .adapter import get_scope, get_reply_id, pick_picture, picture_url
from .core.sql import simpic, randpic, countpic, select_pic
from .core.utils import img2vec

cpic = on_command("countpic", priority=5)
rpic = on_command("randpic", priority=5)
s_simpic = on_command("simpic", priority=5)
pic_listen = on_endswith((".jpg", ".png", ".gif"), priority=50, block=False)
pic_clear = on_command("pic.clear", permission=SUPERUSER, priority=1, block=True)


async def url_to_image(url: str) -> Image:
    if url.startswith("http"):
        return Image(url=url)
    return Image(path=Path(url))


@cpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = get_scope(event)
    try:
        await bot.send(event, f"共查找到 {await countpic(reg, group_id)} 张图片。")
    except Exception as ex:
        await cpic.finish(f"出错了喵~\n\n{ex}")


@pic_listen.handle()
async def _(bot: Bot, event: Event):
    name = event.get_plaintext().strip()
    group_id = get_scope(event)
    try:
        if url := await select_pic(name, group_id):
            await UniMessage(await url_to_image(url)).send()
    except Exception as ex:
        await pic_listen.finish(str(ex))


@rpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    name = args.extract_plain_text().strip()
    group_id = get_scope(event)
    try:
        pic, t = await randpic(name, group_id, True)
        if not pic:
            await rpic.send("404 Not Found.")
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
        await rpic.finish(str(ex))


@s_simpic.handle()
async def _(bot: Bot, event: Event, args: Message = CommandArg()):
    picture = pick_picture(args, event)
    if picture is None:
        await s_simpic.finish("请发送图片后再使用该指令喵~")
    try:
        vec = await img2vec(
            await picture_url(bot, picture),
            title=args.extract_plain_text().strip(),
        )
        if vec is None:
            await s_simpic.finish("图片特征提取失败喵~")
        group_id = get_scope(event)
        sim, pic = await simpic(vec, group_id)
    except Exception as ex:
        await s_simpic.finish(str(ex))

    if pic:
        ret = UniMessage()
        if reply_id := get_reply_id(event):
            ret.append(Reply(reply_id))
        ret.append(Text(f"{pic.name}\n(相似性：{'%.4g' % (min(sim * 100, 100.0))}%)"))
        ret.append(await url_to_image(pic.url))
        await ret.send()
    else:
        await s_simpic.send("没有找到相似的图片喵~")


@pic_clear.handle()
async def _():
    # 清理孤儿图片
    from .core import sql

    if not sql.POOL:
        await pic_clear.finish("数据库未初始化")
    await pic_clear.send("开始清理孤儿图片...")
    img = set(Path("savepic").glob("*"))
    async with sql.POOL.acquire() as conn, conn.transaction():
        async for record in conn.cursor("SELECT name, url FROM picdata;"):
            if not record["url"].startswith("savepic/"):
                continue
            p = Path(record["url"])
            img.remove(p)
    if img:
        await pic_clear.send(f"发现 {len(img)} 张孤儿图片，正在删除...")
        for p in img:
            p.unlink(missing_ok=True)
        await pic_clear.send("删除完成！")
    else:
        await pic_clear.send("没有发现孤儿图片！")

from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from sqlalchemy.exc import DBAPIError
from .rule import BLACK_GROUP
from .pic_sql import countpic

cpic = on_command("countpic", priority=5, permission=BLACK_GROUP)


@cpic.handle()
async def _(bot, event, args=CommandArg()):
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

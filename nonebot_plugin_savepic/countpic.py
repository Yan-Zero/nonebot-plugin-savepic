from nonebot import on_command
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from sqlalchemy.exc import DBAPIError
from .rule import BLACK_GROUP
from .pic_sql import _async_database
from .pic_sql import select
from .pic_sql import AsyncSession
from .pic_sql import sa
from .model import PicData


cpic = on_command("countpic", priority=5, permission=BLACK_GROUP)


async def countpic(reg: str, group: str = "globe") -> int:
    reg = reg.strip()
    if not reg:
        reg = ".*"
    async with AsyncSession(_async_database) as db_session:
        pics = await db_session.scalar(
            select(sa.func.count()).select_from(
                select(PicData)
                .where(sa.or_(PicData.group == group, PicData.group == "globe"))
                .where(PicData.name != "")
                .where(PicData.name.regexp_match(reg, flags="i"))
            )
        )
        if pics:
            return pics
        return 0


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

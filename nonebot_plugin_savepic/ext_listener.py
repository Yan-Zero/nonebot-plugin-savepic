from nonebot import on_message
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.internal.adapter.bot import Bot
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent

from .pic_sql import load_pic, select_pic


async def endswith_pic(event: MessageEvent):
    text = event.message.extract_plain_text().strip()
    if " " in text:
        return False
    return text.endswith((".jpg", ".png", ".gif"))


pic_listen = on_message(rule=endswith_pic)


@pic_listen.handle()
async def _(bot: Bot, event: MessageEvent):
    name = event.message.extract_plain_text().strip()
    group_id = (
        "globe"
        if not isinstance(event, GroupMessageEvent)
        else f"qq_group:{event.group_id}"
    )
    try:
        pic = await select_pic(name, group_id)
        if pic:
            file_ = await load_pic(pic.url)
            await bot.send(event, V11Seg.image(file=file_))
    except Exception as ex:
        await pic_listen.finish(str(ex))

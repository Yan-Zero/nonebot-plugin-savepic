from nonebot import require
from nonebot import get_driver

require("nonebot_plugin_datastore")

from nonebot import on_command, on_message
from nonebot.params import CommandArg, Arg
from nonebot.adapters.onebot.v11.message import Message as V11Msg
from nonebot.adapters.onebot.v11.message import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.event import MessageEvent
from nonebot.adapters.onebot.v11.event import GroupMessageEvent
from nonebot.matcher import Matcher
from nonebot.typing import T_State

from asyncpg.exceptions import InvalidRegularExpressionError

from .config import Config
from .pic_sql import savepic, rename, delete, write_pic, randpic, load_pic, select_pic
from .rule import PIC_AMDIN

INVALID_FILENAME_CHARACTERS = r'\/:*?"<>|'

global_config = get_driver().config
p_config = Config.parse_obj(global_config)

rpic = on_command("randpic", aliases={"随机图"}, priority=5)
@rpic.handle()
async def _(bot: Bot, event, args: V11Msg = CommandArg()):
    reg = args.extract_plain_text().strip()
    group_id = 'globe' if not isinstance(event, GroupMessageEvent) else f"qq_group:{event.group_id}"
    try:
        pic = await randpic(reg, group_id)
        if pic:
            file_ = await load_pic(pic.url)
            await bot.send(event, V11Msg([pic.name + "\n", V11Seg.image(file=file_)]))
    except InvalidRegularExpressionError:
        await rpic.finish('正则表达式错误')
    except Exception as ex:
        await rpic.finish(str(ex))

spic = on_command("savepic", aliases={"存图"}, priority=5)
@spic.handle()
async def _(bot: Bot, matcher: Matcher, event: GroupMessageEvent, state: T_State, args: V11Msg = CommandArg()):
    if not args:
        await spic.finish('''用法:
/savepic <文件名> <图片>
/savepic -g <文件名> <全局图片>
/savepic -d <文件名> 删除图图片
/savepic -m <原文件名> <新文件名> 重命名图片''')
    params = args.extract_plain_text().strip().split()
    state['savepiv_group'] = 'globe' if '-g' in params and await PIC_AMDIN(bot, event) else f"qq_group:{event.group_id}"
    _d = '-d' in params
    _m = '-m' in params
    if _d:
        params.remove('-d')
    if _m:
        params.remove('-m')
    if '-g' in params:
        params.remove('-g')

    if not params:
        await spic.finish("文件名？")
    filename = params[0].strip()
    for c in INVALID_FILENAME_CHARACTERS:
        filename = filename.replace(c, "-")
    if not filename.endswith(('.jpg', '.png', '.gif')):
        filename += '.jpg'

    if _d:
        if not await PIC_AMDIN(bot, event):
            await spic.finish('不支持选项 -d')
        try:
            await delete(filename, state['savepiv_group'])
        except Exception as ex:
            await spic.finish(str(ex))
        await spic.finish('图片已删除')

    if _m:
        if not await PIC_AMDIN(bot, event):
            await spic.finish('不支持选项 -m')
        if len(params) <= 1:
            await spic.finish("目标文件名？")
        for c in INVALID_FILENAME_CHARACTERS:
            params[1] = params[1].replace(c, "-")
        if not params[1].endswith(('.jpg', '.png', '.gif')):
            params[1] += '.jpg'

        try:
            await rename(filename, params[1],  f"qq_group:{event.group_id}", state['savepiv_group'])
        except Exception as ex:
            await spic.finish(str(ex))
        await spic.finish('图片已重命名')

    pic = await select_pic(filename, state['savepiv_group'])
    if pic and pic.group == state['savepiv_group']:
        spic.finish("图片已存在。")
    picture = args.get('image')
    state['savepiv_filename'] = filename
    if not picture and event.reply:
        picture = event.reply.message.get('image')
    if picture:
        matcher.set_arg('picture', picture)

@spic.got('picture', "图呢？")
async def _(bot: Bot, event: GroupMessageEvent, state: T_State, picture: V11Msg = Arg()):
    picture = picture.get('image')
    if not picture:
        await spic.finish('6，这也不是图啊')
    try:
        dir = await write_pic(picture[0].data['url'], p_config.savepic_dir)
    except Exception as ex:
        await spic.finish("存图失败。" + '\n' + str(ex))
    try:
        await savepic(state['savepiv_filename'], dir, state['savepiv_group'])
        await spic.send("保存成功")
    except Exception as ex:
        await spic.finish(str(ex))

async def endswith_pic(event: MessageEvent):
    text = event.message.extract_plain_text().strip()
    if ' ' in text:
        return False
    return text.endswith(('.jpg', '.png', '.gif'))

pic_listen = on_message(rule=endswith_pic)
@pic_listen.handle()
async def _(bot: Bot, event: MessageEvent):
    name = event.message.extract_plain_text().strip()
    group_id = 'globe' if not isinstance(event, GroupMessageEvent) else f"qq_group:{event.group_id}"
    try:
        pic = await select_pic(name, group_id)
        if pic:
            file_ = await load_pic(pic.url)
            await bot.send(event, V11Seg.image(file=file_))
    except Exception as ex:
        await rpic.finish(str(ex))

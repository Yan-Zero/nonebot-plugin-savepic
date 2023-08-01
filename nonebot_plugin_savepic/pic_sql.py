from nonebot_plugin_datastore import create_session
import sqlalchemy as sa
from sqlalchemy import select, update
import hashlib
import httpx
import os
import random
from sqlalchemy.sql import func
from nonebot_plugin_datastore.db import post_db_init

from .model import PicData

httpx_async = None

async def load_pic(url: str)-> bytes:
    global httpx_async
    if url.startswith("http"):
        if not httpx_async:
            httpx_async = httpx.AsyncClient()
        resp = await httpx_async.get(url)
        resp.raise_for_status()
        return resp.content
    if os.path.exists(url):
        with open(url, 'rb') as f:
            return f.read()
    raise Exception("不支持的统一资源定位器")

def del_pic(url: str):
    if os.path.exists(url):
        os.remove(url)

async def write_pic(url: str, des_dir: str = None) -> str:
    if not des_dir:
        des_dir = 'savepic'
    if not os.path.exists(des_dir):
        os.makedirs(des_dir)

    byte = await load_pic(url)
    filename = hashlib.sha256(byte).hexdigest()
    while os.path.exists(os.path.join(des_dir, filename)):
        filename = hashlib.sha256((filename + str(random.randint(0, 100000))).encode()).hexdigest()
    with open(os.path.join(des_dir, filename), 'wb+') as f:
        f.write(byte)
    return os.path.join(des_dir, filename)

async def select_pic(filename: str, group: str):
    async with create_session() as db_session:
        pic = await db_session.scalar(select(PicData)
        .where(PicData.name == filename)
        .where(PicData.group == group))
        if pic:
            return pic

        pic = await db_session.scalar(select(PicData)
        .where(PicData.name == filename)
        .where(PicData.group == 'globe'))
        if pic:
            return pic

async def savepic(filename: str, dir: str, group_id: str):
    pic = PicData(
        group = group_id,
        name = filename,
        url = dir,
    )
    async with create_session() as db_session:
        # select the name == ""
        despic = await select_pic(filename, group_id)
        if despic and despic.group == group_id:
            raise Exception("文件名已存在。")
        
        if random.randint(1, 10) == 1:
            empty = await db_session.scalar(select(PicData).where(PicData.name == ""))
        else:
            empty = None

        if empty:
            empty.group = group_id
            empty.url = dir
            empty.name = filename
            await db_session.merge(empty)
        else:
            db_session.add(pic)
        await db_session.commit()

@post_db_init
async def init():
    if not os.path.exists('history_savepic'):
        return
    for root, dirs, files in os.walk('history_savepic'):
        group = root.split('/')[-1]
        for file in files:
            dir = os.path.join("savepic", file.replace(' ', ''))
            if os.path.exists(dir):
                dir = await write_pic(os.path.join(root, file))
                os.remove(os.path.join(root, file))
            else:
                os.rename(os.path.join(root, file), dir)

            try:
                await savepic(file, dir, group)
                print(f"save {file} to {group}")
            except Exception as ex:
                print(ex)
                os.remove(dir)

async def rename(ori: str, des: str, s_group: str, d_group: str):
    async with create_session() as db_session:
        pic = await db_session.scalar(select(PicData).where(
            PicData.name == ori
        ).where(sa.or_(PicData.group == s_group, PicData.group == "globe")))
        if not pic:
            raise Exception("重命名失败，没有找到图片")
        despic = await db_session.scalar(select(PicData).where(
            sa.and_(PicData.name == des, PicData.group == d_group)
        ))
        if despic:
            raise Exception("重命名失败，目标文件名已存在")
        pic.name = des
        pic.group = d_group
        
        await db_session.merge(pic)
        await db_session.commit()

async def delete(filename: str, group: str):
    async with create_session() as db_session:
        pic = await db_session.scalar(select(PicData).where(
            sa.and_(PicData.name == filename, PicData.group == group)
        ))
        if pic:
            del_pic(pic.url)
            pic.name = ""
            await db_session.merge(pic)
            await db_session.commit()
        else:
            raise Exception("删除失败，没有找到图片")

async def randpic(reg: str, group: str = "globe") -> PicData:
    reg = reg.strip()
    if not reg:
        reg = ".*"
    async with create_session() as db_session:
        pic = await db_session.scalar(select(PicData)
        .where(sa.or_(PicData.group == group, PicData.group == "globe"))
        .where(PicData.name != "")
        .order_by(func.random())
        .where(PicData.name.regexp_match(reg))
        )
        if pic:
            return pic
import sqlalchemy as sa
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
from nonebot import get_driver
import os
import random
import csv
import hashlib
from sqlalchemy import cast

from .model import PicData, BIT
from .picture import load_pic, p_hash
from .config import Config

gdriver = get_driver()
p_config = Config.parse_obj(gdriver.config)
_async_database = None


def AsyncDatabase():
    if not _async_database:
        raise RuntimeError("Database is not initialized")
    return _async_database


def del_pic(url: str):
    if os.path.exists(url):
        os.remove(url)


async def write_pic(url: str, des_dir: str = None) -> str:
    if not des_dir:
        des_dir = "savepic"
    if not os.path.exists(des_dir):
        os.makedirs(des_dir)

    byte = await load_pic(url)
    filename = hashlib.sha256(byte).hexdigest()
    while os.path.exists(os.path.join(des_dir, filename)):
        filename += "_"
    with open(os.path.join(des_dir, filename), "wb") as f:
        f.write(byte)
    return os.path.join(des_dir, filename)


async def select_pic(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group)
        )
        if pic:
            return pic

        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == "globe")
        )
        if pic:
            return pic


async def savepic(
    filename: str,
    url: str,
    hash: bytes,
    group_id: str = "globe",
    collision_allow: bool = False,
):
    pic = PicData(
        group=group_id,
        name=filename,
        url=url,
        phash=hash,
    )
    async with AsyncSession(_async_database) as db_session:
        # select the name == ""
        despic = await select_pic(filename, group_id)
        if despic and despic.group == group_id:
            raise Exception("文件名已存在。")
        despic = await db_session.scalar(
            select(PicData)
            .where(PicData.group == group_id)
            .where(
                sa.func.bit_count(PicData.phash.bitwise_xor(cast(hash, BIT(256)))) <= 7
            )
        )
        if despic and not collision_allow:
            raise Exception("相似图片已存在。" + "\n" + despic.name)

        if random.randint(1, 10) == 1:
            empty = await db_session.scalar(select(PicData).where(PicData.name == ""))
        else:
            empty = None

        if empty:
            empty.group = group_id
            empty.url = url
            empty.name = filename
            empty.phash = pic.phash
            await db_session.merge(empty)
        else:
            db_session.add(pic)
        await db_session.commit()


async def init_db():
    # check if the table exists
    global _async_database
    _async_database = create_async_engine(
        p_config.savepic_sqlurl, pool_pre_ping=True, pool_size=25, max_overflow=20
    )

    try:
        metadata = sa.MetaData()
        table = sa.Table(
            "picdata",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.TEXT, nullable=False),
            sa.Column("group", sa.TEXT, nullable=False),
            sa.Column("url", sa.TEXT, nullable=False),
            sa.Column("phash", BIT(256), nullable=False),
        )
        async with _async_database.begin() as conn:
            await conn.run_sync(metadata.create_all)
    except Exception:
        pass


@gdriver.on_startup
async def _():
    if not p_config.savepic_sqlurl:
        raise Exception("请配置 savepic_sqlurl")

    await init_db()
    if os.path.exists("savepic_picdata.csv"):
        # 加载旧版数据
        print("加载旧版数据")
        failed = []
        with open("savepic_picdata.csv", "r") as f:
            for i in csv.reader(f):
                _, name, group, url = i
                if not name or url == "url":
                    continue
                t = await select_pic(name, group)
                if t and t.group == group:
                    continue
                p_hash_ = p_hash(await load_pic(url))
                print(i)
                try:
                    await savepic(name, url, p_hash_, group, True)
                except Exception as ex:
                    print(ex)
                    failed.append(i)
        os.remove("savepic_picdata.csv")
        with open("savepic.csv", "w+") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "group", "url"])
            for i in failed:
                writer.writerow(i)


async def rename(ori: str, des: str, s_group: str, d_group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == ori)
            .where(sa.or_(PicData.group == s_group, PicData.group == "globe"))
        )
        if not pic:
            raise Exception("重命名失败，没有找到图片")
        despic = await db_session.scalar(
            select(PicData).where(
                sa.and_(PicData.name == des, PicData.group == d_group)
            )
        )
        if despic:
            raise Exception("重命名失败，目标文件名已存在")
        pic.name = des
        pic.group = d_group

        await db_session.merge(pic)
        await db_session.commit()


async def delete(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData).where(
                sa.and_(PicData.name == filename, PicData.group == group)
            )
        )
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
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != "")
            .order_by(sa.func.random())
            .where(PicData.name.regexp_match(reg))
        )
        if pic:
            return pic

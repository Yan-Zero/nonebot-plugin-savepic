import hashlib
import pathlib
import httpx
import sqlalchemy as sa

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from nonebot import get_driver
from ..model import PicLife
from ..config import plugin_config

# 异步连接到 plugin_config.local_sqlite_path
_async_database = None


@get_driver().on_startup
async def init_db():
    # check if the table exists
    global _async_database
    _async_database = create_async_engine(
        plugin_config.local_sqlite_path,
    )
    try:
        metadata = sa.MetaData()
        sa.Table(
            "piclife",
            metadata,
            sa.Column("url", sa.Text, primary_key=True),
            sa.Column("life", sa.Integer, default=0),
        )
        async with _async_database.begin() as conn:
            await conn.run_sync(metadata.create_all)
    except Exception as ex:
        print(ex)


async def del_pic(url: str | pathlib.Path):
    if isinstance(url, pathlib.Path):
        url = url.as_posix()
    if url.startswith("http"):
        return
    if isinstance(url, str):
        _ = pathlib.Path(url)
    else:
        _ = url

    async with AsyncSession(_async_database) as session:
        if life := await session.get(PicLife, url):
            if life.life > 0:
                life.life -= 1
                await session.commit()
                return
            await session.delete(life)
            await session.commit()
    if _.exists():
        _.unlink()


async def load_pic(url: str) -> bytes:
    if url.startswith("http"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    if pathlib.Path(url).exists():
        with open(url, "rb") as f:
            return f.read()
    raise Exception(f"不支持的 URL\n{url}")


async def write_pic(url: str, des_dir: str = None) -> str:
    if not des_dir:
        des_dir = "savepic"
    path = pathlib.Path(des_dir)
    path.mkdir(parents=True, exist_ok=True)

    byte = await load_pic(url)
    file = path / hashlib.sha256(byte).hexdigest()

    async with AsyncSession(_async_database) as session:
        if life := await session.get(PicLife, url):
            life.life += 1
            await session.commit()
            return file.as_posix()
        life = PicLife(url=url)
        session.add(life)
        await session.commit()

    with open(file, "wb") as f:
        f.write(byte)
    return file.as_posix()

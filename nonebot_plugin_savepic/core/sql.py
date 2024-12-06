import asyncpg
import sqlalchemy as sa

from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
from nonebot import get_driver

from .error import SameNameException
from .error import SimilarPictureException
from .error import NoPictureException
from .utils import word2vec
from .utils import img2vec
from .fileio import del_pic
from .fileio import load_pic
from ..model import PicData
from ..config import plugin_config


gdriver = get_driver()
_async_database = None
_async_embedding_database = None


async def update_vec(pic: PicData):
    if pic is None:
        return
    if not pic.u_vec_text and not pic.u_vec_img:
        return

    async with AsyncSession(_async_database) as db_session:
        if pic.u_vec_text:
            pic.u_vec_text = False
            await _async_embedding_database.execute(
                "UPDATE savepic_word2vec SET embedding = $1 WHERE id = $2",
                str(await word2vec(pic.name)),
                pic.id,
            )
            await db_session.merge(pic)
        if pic.u_vec_img:
            pic.u_vec_img = False
            await _async_embedding_database.execute(
                "UPDATE savepic_img2vec SET embedding = $1 WHERE id = $2",
                str(await img2vec(await load_pic(pic.url)), ""),
                pic.id,
            )
        await db_session.commit()


async def select_pic(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        if pic := await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group)
        ):
            await update_vec(pic)
            return pic
        return await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == "globe")
        )


async def savepic(
    filename: str,
    url: str,
    img_vec: list[float],
    group_id: str = "globe",
    collision_allow: bool = False,
):
    pic = PicData(
        group=group_id, name=filename, url=url, u_vec_img=False, u_vec_text=False
    )
    async with AsyncSession(_async_database) as db_session:
        despic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group_id)
        )
        if despic:
            raise SameNameException(despic.name)
        if not collision_allow:
            if datas := await _async_embedding_database.fetch(
                (
                    "SELECT id, 1 - (embedding <=> $1) AS similarity FROM savepic_img2vec "
                    "WHERE embedding IS NOT NULL and embedding <=> $1 < 0.08 "
                    "ORDER BY similarity DESC LIMIT 8;"
                ),
                str(img_vec),
            ):
                for i in datas:
                    while pic := await db_session.scalar(
                        select(PicData)
                        .where(
                            sa.or_(PicData.group == group_id, PicData.group == "globe")
                        )
                        .where(PicData.id == i["id"])
                        .where(PicData.name != "")
                    ):
                        raise SimilarPictureException(
                            pic.name, i["similarity"], pic.url
                        )

        empty = await db_session.scalar(select(PicData).where(PicData.name == ""))
        if empty:
            pic.id = empty.id
            await db_session.merge(pic)
        else:
            db_session.add(pic)
        await db_session.flush()

        await _async_embedding_database.execute(
            (
                "INSERT INTO savepic_word2vec (id, embedding) VALUES ($1, $2) "
                "ON CONFLICT (id) DO UPDATE SET embedding = $2"
            ),
            pic.id,
            str(await word2vec(filename)),
        )
        await _async_embedding_database.execute(
            (
                "INSERT INTO savepic_img2vec (id, embedding) VALUES ($1, $2) "
                "ON CONFLICT (id) DO UPDATE SET embedding = $2"
            ),
            pic.id,
            str(img_vec),
        )
        await db_session.commit()


async def simpic(img_vec: list[float], group: str = "globe", ignore_min: bool = False):
    async with AsyncSession(_async_database) as db_session:
        if datas := await _async_embedding_database.fetch(
            (
                "SELECT id, 1 - (embedding <=> $1) AS similarity FROM savepic_img2vec "
                "WHERE embedding IS NOT NULL "
                + ("" if ignore_min else "and embedding <=> $1 < 0.35 ")
                + "ORDER BY similarity DESC LIMIT 10;"
            ),
            str(img_vec),
        ):
            for i in datas:
                while pic := await db_session.scalar(
                    select(PicData)
                    .where(sa.or_(PicData.group == group, PicData.group == "globe"))
                    .where(PicData.id == i["id"])
                    .where(PicData.name != "")
                ):
                    return i["similarity"], pic
        return None, None


async def rename(ori: str, des: str, s_group: str, d_group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == ori)
            .where(sa.or_(PicData.group == s_group))
        )
        if not pic:
            raise NoPictureException(ori)

        despic = await db_session.scalar(
            select(PicData).where(PicData.name == des).where(PicData.group == d_group)
        )
        if despic:
            raise SameNameException(despic.name)

        pic.name = des
        pic.group = d_group
        pic.u_vec_text = False
        await _async_embedding_database.execute(
            "UPDATE savepic_word2vec SET embedding = $1 WHERE id = $2",
            str(await word2vec(des)),
            pic.id,
        )
        await db_session.merge(pic)
        await db_session.commit()


async def delete(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData).where(
                sa.and_(PicData.name == filename, PicData.group == group)
            )
        )
        if not pic:
            raise NoPictureException(filename)
        await del_pic(pic.url)
        pic.name = ""
        await db_session.merge(pic)
        await _async_embedding_database.execute(
            "UPDATE savepic_word2vec SET embedding = NULL WHERE id = $1", pic.id
        )
        await db_session.commit()


async def regexp_pic(reg: str, group: str = "globe") -> PicData:
    reg = reg.strip()
    if not reg:
        reg = ".*"
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != "")
            .order_by(sa.func.random())
            .where(PicData.name.regexp_match(reg, flags="i"))
        )
        if pic:
            return pic


async def randpic(
    name: str, group: str = "globe", vector: bool = False
) -> tuple[PicData, str]:
    name = name.strip().replace("%", r"\%").replace("_", r"\_")

    async with AsyncSession(_async_database) as db_session:
        if not name:
            return (
                await db_session.scalar(
                    select(PicData)
                    .where(sa.or_(PicData.group == group, PicData.group == "globe"))
                    .where(PicData.name != "")
                    .order_by(sa.func.random())
                ),
                "",
            )

        if pic := await db_session.scalar(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name.ilike(f"%{name}%"))
            .order_by(sa.func.random())
        ):
            await update_vec(pic)
            return pic, ""

        if not vector:
            return None, ""

        datas = await _async_embedding_database.fetch(
            (
                "SELECT id FROM savepic_word2vec "
                "WHERE embedding IS NOT NULL and embedding <=> $1 <= 0.45 "
                "ORDER BY embedding <#> $1 LIMIT 8;"
            ),
            str(await word2vec(name)),
        )
        if pic := await db_session.scalar(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.id.in_([i["id"] for i in datas]))
            .where(PicData.name != "")
            .order_by(sa.func.random())
        ):
            return pic, "（语义向量相似度检索）"

        if plugin_config.notfound_with_jpg:
            datas = await _async_embedding_database.fetch(
                (
                    "SELECT id FROM savepic_word2vec "
                    "WHERE embedding IS NOT NULL and embedding <=> $1 <= 0.45 "
                    "ORDER BY embedding <#> $1 LIMIT 8;"
                ),
                str(await word2vec(name + ".jpg")),
            )
            if pic := await db_session.scalar(
                select(PicData)
                .where(sa.or_(PicData.group == group, PicData.group == "globe"))
                .where(PicData.id.in_([i["id"] for i in datas]))
                .where(PicData.name != "")
                .order_by(sa.func.random())
            ):
                return pic, "（语义向量相似度检索）"

        return None, False


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


async def listpic(reg: str, group: str = "globe", pages: int = 0) -> list[str]:
    reg = reg.strip()
    if not reg:
        reg = ".*"

    pages = max(pages - 1, 0)
    _count = min(
        max(
            1, plugin_config.count_per_page_in_list * plugin_config.max_page_in_listpic
        ),
        1000,
    )

    async with AsyncSession(_async_database) as db_session:
        pics = await db_session.scalars(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != "")
            .where(PicData.name.regexp_match(reg, flags="i"))
            .order_by(PicData.name)
            .offset(pages * plugin_config.count_per_page_in_list)
            .limit(_count)
        )
        if pics:
            return [str(pic.name) for pic in pics]


async def init_db():
    # check if the table exists
    global _async_database, _async_embedding_database
    _async_database = create_async_engine(
        plugin_config.savepic_sqlurl,
        future=True,
        pool_size=2,
        max_overflow=0,
    )
    if plugin_config.embedding_sqlurl.startswith("postgresql+asyncpg"):
        plugin_config.embedding_sqlurl = (
            "postgresql" + plugin_config.embedding_sqlurl[18:]
        )
    _async_embedding_database = await asyncpg.create_pool(
        plugin_config.embedding_sqlurl,
        min_size=1,
        max_size=2,
    )

    try:
        metadata = sa.MetaData()
        sa.Table(
            "picdata",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.TEXT, nullable=False),
            sa.Column("group", sa.TEXT, nullable=False),
            sa.Column("url", sa.TEXT, nullable=False),
            sa.Column("u_vec_img", sa.BOOLEAN, nullable=False),
            sa.Column("u_vec_text", sa.BOOLEAN, nullable=False),
        )
        async with _async_database.begin() as conn:
            await conn.run_sync(metadata.create_all)
    except Exception as ex:
        print(ex)

    if not (
        await _async_embedding_database.fetch(
            (
                "SELECT EXISTS "
                "(SELECT FROM pg_tables "
                "WHERE tablename = 'savepic_word2vec');"
            )
        )
    )[0]["exists"]:
        await _async_embedding_database.execute(
            (
                "CREATE TABLE savepic_word2vec (\n"
                "  id bigserial PRIMARY KEY, \n"
                "  embedding vector(1024)\n"
                ");"
            )
        )

    if not (
        await _async_embedding_database.fetch(
            (
                "SELECT EXISTS "
                "(SELECT FROM pg_tables "
                "WHERE tablename = 'savepic_img2vec');"
            )
        )
    )[0]["exists"]:
        await _async_embedding_database.execute(
            (
                "CREATE TABLE savepic_img2vec (\n"
                "  id bigserial PRIMARY KEY, \n"
                "  embedding vector(1024)\n"
                ");"
            )
        )


@gdriver.on_startup
async def _():
    if not plugin_config.savepic_sqlurl:
        raise Exception("请配置 savepic_sqlurl")

    await init_db()

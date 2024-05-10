import sqlalchemy as sa
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
import asyncpg
from nonebot import get_driver
import dashscope
import pathlib
from pinecone import Pinecone, ServerlessSpec

from .model import PicData
from .picture import del_pic
from .ai_utils import word2vec
from .ai_utils import file2vec
from .config import Config
from .error import SameNameException
from .error import SimilarPictureException
from .error import NoPictureException

gdriver = get_driver()
p_config = Config.parse_obj(gdriver.config)
_async_database = None
_pincone_index = None
_async_embedding_database = None


def AsyncDatabase():
    if not _async_database:
        raise RuntimeError("Database is not initialized")
    return _async_database


async def select_pic(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group)
        )
        if pic:
            await update_vec(pic)
            return pic
        return await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == "globe")
        )


# async def get_most_similar_pic(
#     img_vec: list[float],
#     group_id: str,
#     ignore_diagonal: bool = False,
#     ignore_min: bool = False,
# ) -> tuple[float, PicData]:
#     async with AsyncSession(_async_database) as db_session:
#         ret = _pincone_index.query(img_vec, top_k=20)["matches"]
#         if not ret:
#             return None, None
#         if not ret[0]["id"]:
#             return None, None
#         if ignore_diagonal and ret[0]["score"] >= 0.999:
#             ret.pop(0)

#         for i in ret:
#             if i["score"] < 0.65 and not ignore_min:
#                 return None, None
#             if i["id"]:
#                 despic = await db_session.scalar(
#                     select(PicData)
#                     .where(PicData.id == int(i["id"]))
#                     .where(PicData.name != "")
#                     .where(sa.or_(PicData.group == group_id, PicData.group == "globe"))
#                 )
#                 if despic:
#                     return i["score"], despic

#         return None, None


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

        # if not collision_allow:
        #     ret = _pincone_index.query(img_vec, top_k=25)["matches"]
        #     for i in ret:
        #         if i["score"] and i["score"] < 0.98:
        #             break
        #         despic = await db_session.scalar(
        #             select(PicData)
        #             .where(PicData.id == int(ret[0]["id"]))
        #             .where(sa.or_(PicData.group == group_id, PicData.group == "globe"))
        #         )
        #         if despic:
        #             raise SimilarPictureException(despic.name, i["score"], despic.url)

        empty = await db_session.scalar(select(PicData).where(PicData.name == ""))
        if empty:
            pic.id = empty.id
            await db_session.merge(pic)
        else:
            db_session.add(pic)
        await db_session.flush()

        # _pincone_index.upsert([(str(pic.id), img_vec)])
        await _async_embedding_database.execute(
            (
                "INSERT INTO savepic_word2vec (id, embedding) VALUES ($1, $2) "
                "ON CONFLICT (id) DO UPDATE SET embedding = $2"
            ),
            pic.id,
            str(word2vec(filename)),
        )
        await db_session.commit()


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
            str(word2vec(des)),
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
        del_pic(pic.url)
        pic.name = ""
        await db_session.merge(pic)
        # _pincone_index.delete(ids=[str(pic.id)])
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
            str(word2vec(name)),
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


async def update_vec(pic: PicData):
    if not pic:
        return
    if not pic.u_vec_text:  # and not pic.u_vec_img:
        return
    if pic.u_vec_text:
        pic.u_vec_text = False
        await _async_embedding_database.execute(
            "UPDATE savepic_word2vec SET embedding = $1 WHERE id = $2",
            str(word2vec(pic.name)),
            pic.id,
        )
    # if pic.u_vec_img:
    #     pic.u_vec_img = False
    #     _pincone_index.upsert(
    #         [(str(pic.id), file2vec(pathlib.Path(pic.url), pic.name))]
    #     )
    async with AsyncSession(_async_database) as db_session:
        db_session.merge(pic)
        await db_session.flush()
        db_session.commit()


async def listpic(reg: str, group: str = "globe", pages: int = 0) -> list[str]:
    reg = reg.strip()
    if not reg:
        reg = ".*"
    pages -= 1
    async with AsyncSession(_async_database) as db_session:
        pics = await db_session.scalars(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != "")
            .where(PicData.name.regexp_match(reg, flags="i"))
            .order_by(PicData.name)
            .offset((0 if pages < 0 else pages) * 10)
            .limit(10)
        )
        if pics:
            return [str(pic.name) for pic in pics]


async def init_db():
    # check if the table exists
    global _async_database, _pincone_index, _async_embedding_database
    _async_database = create_async_engine(
        p_config.savepic_sqlurl,
        future=True,
        # connect_args={"statement_cache_size": 0},
    )
    if p_config.embedding_sqlurl.startswith("postgresql+asyncpg"):
        p_config.embedding_sqlurl = "postgresql" + p_config.embedding_sqlurl[18:]
    _async_embedding_database = await asyncpg.create_pool(
        p_config.embedding_sqlurl  # , statement_cache_size=0
    )
    dashscope.api_key = p_config.dashscope_api

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
                "  embedding vector(1536)\n"
                ");"
            )
        )

    if not p_config.pinecone_apikey:
        raise Exception("请配置 pinecone_apikey")
    if not p_config.pinecone_environment:
        raise Exception("请配置 pinecone_environment")

    pc = Pinecone(api_key=p_config.pinecone_apikey)
    if p_config.pinecone_index not in pc.list_indexes().names():
        pc.create_index(
            name=p_config.pinecone_index,
            dimension=1536,
            metric="euclidean",
            spec=ServerlessSpec(cloud="aws", region="us-west-2"),
        )
    if not _pincone_index:
        _pincone_index = pc.Index(p_config.pinecone_index)


@gdriver.on_startup
async def _():
    if not p_config.savepic_sqlurl:
        raise Exception("请配置 savepic_sqlurl")

    await init_db()
    # if os.path.exists("savepic_picdata.json"):
    #     print("加载附加数据")
    #     with open("savepic_picdata.json", "r") as f:
    #         files = json.load(f)
    #     failed = []
    #     for i in files:
    #         url = os.path.join("savepic", i)
    #         try:
    #             async with AsyncSession(_async_database) as db_session:
    #                 pic = await db_session.scalar(
    #                     select(PicData)
    #                     .where(PicData.url == url)
    #                     .where(PicData.name != "")
    #                 )
    #                 if pic:
    #                     _pincone_index.upsert([(str(pic.id), files[i])])
    #                     print(f"{pic.name} 加载成功")
    #         except Exception as ex:
    #             print(ex)
    #             failed.append(url)
    #     os.remove("savepic_picdata.json")
    #     print("向量数据加载完成")

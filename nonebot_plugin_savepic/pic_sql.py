import sqlalchemy as sa
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select
import asyncpg
from nonebot import get_driver
import dashscope
from dashscope import TextEmbedding
import pinecone

from http import HTTPStatus

from .model import PicData
from .picture import del_pic
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

def word2vec(word: str) -> list[float]:
    if not p_config.dashscope_api:
        raise KeyError("Hmmm, 没有填写 dashscope 的 apikey")
    
    resp = TextEmbedding.call(
        model=TextEmbedding.Models.text_embedding_v1, input=word, text_type="query"
    )
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError("Dashscope API Error")
    return resp.output["embeddings"][0]["embedding"]


async def select_pic(filename: str, group: str):
    async with AsyncSession(_async_database) as db_session:
        pic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group)
        )
        if pic:
            return pic
        return await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == "globe")
        )


async def get_most_similar_pic(
    img_vec: list[float],
    group_id: str,
    ignore_diagonal: bool = False,
    ignore_min: bool = False,
) -> tuple[float, PicData]:
    if not p_config.pinecone_apikey:
        raise KeyError("Pinecone APIKey 未填写")

    async with AsyncSession(_async_database) as db_session:
        ret = _pincone_index.query(img_vec, top_k=20)["matches"]
        if not ret:
            return None, None
        if not ret[0]["id"]:
            return None, None
        if ignore_diagonal and ret[0]["score"] >= 0.999:
            ret.pop(0)

        for i in ret:
            if i["score"] < 0.65 and not ignore_min:
                return None, None
            if i["id"]:
                despic = await db_session.scalar(
                    select(PicData)
                    .where(PicData.id == int(i["id"]))
                    .where(PicData.name != "")
                    .where(sa.or_(PicData.group == group_id, PicData.group == "globe"))
                )
                if despic:
                    return i["score"], despic

        return None, None


async def savepic(
    filename: str,
    url: str,
    img_vec: list[float],
    group_id: str = "globe",
    collision_allow: bool = False,
):
    pic = PicData(
        group=group_id,
        name=filename,
        url=url,
    )
    async with AsyncSession(_async_database) as db_session:
        despic = await db_session.scalar(
            select(PicData)
            .where(PicData.name == filename)
            .where(PicData.group == group_id)
        )
        if despic:
            raise SameNameException(despic.name)
        
        if p_config.pinecone_apikey and not collision_allow:
            ret = _pincone_index.query(img_vec, top_k=25)["matches"]
            for i in ret:
                if i["score"] and i["score"] < 0.98:
                    break
                despic = await db_session.scalar(
                    select(PicData)
                    .where(PicData.id == int(ret[0]["id"]))
                    .where(sa.or_(PicData.group == group_id, PicData.group == "globe"))
                )
                if despic:
                    raise SimilarPictureException(despic.name, i["score"], despic.url)

        empty = await db_session.scalar(select(PicData).where(PicData.name == ""))
        if empty:
            pic.id = empty.id
            await db_session.merge(pic)
        else:
            db_session.add(pic)
        await db_session.flush()

        if _pincone_index:
            _pincone_index.upsert([(str(pic.id), img_vec)])
        
        if p_config.dashscope_api:
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
        if _pincone_index:
            _pincone_index.delete(ids=[str(pic.id)])
        if p_config.dashscope_api:
            await _async_embedding_database.execute(
                "UPDATE savepic_word2vec SET embedding = NULL WHERE id = $1", pic.id
            )
        await db_session.commit()


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
            return pic, ""
        if not vector:
            return None, ""
        if not p_config.dashscope_api:
            return None, False
        
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


async def regexp_pic(reg: str, group: str = "globe") -> PicData:
    if "postgresql" not in p_config.savepic_sqlurl:
        raise TypeError("正则匹配搜索只能 PGSQL，不如使用randpic（ilike匹配）")
    
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


async def countpic(reg: str, group: str = "globe") -> int:
    """ emmm, pgsql 之外的使用 ilike，兼容性并未测试。 """
    reg = reg.strip()
    async with AsyncSession(_async_database) as db_session:
        sql = (select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != ""))
        if "postgresql" in p_config.savepic_sqlurl:
            if not reg:
                reg = ".*"
            pics = await db_session.scalar(
                select(sa.func.count()).select_from(
                    sql.where(PicData.name.regexp_match(reg, flags="i"))
                )
            )
        else:
            pics = await db_session.scalar(
                select(sa.func.count()).select_from(
                    sql.where(PicData.name.ilike(reg))
                )
            )
        if pics:
            return pics
        return 0


async def listpic(reg: str, group: str = "globe", pages: int = 0) -> list[str]:
    pages -= 1
    if pages < 0:
        pages = 0
    if "postgresql" not in p_config.savepic_sqlurl:
        raise TypeError("正则匹配搜索只能 PGSQL")

    reg = reg.strip()
    async with AsyncSession(_async_database) as db_session:
        pics = await db_session.scalars(
            select(PicData)
            .where(sa.or_(PicData.group == group, PicData.group == "globe"))
            .where(PicData.name != "")
            .where(PicData.name.regexp_match(reg, flags="i"))
            .order_by(PicData.name)
            .offset(pages * 10)
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
    )

    if p_config.embedding_sqlurl.startswith("postgresql+asyncpg"):
        p_config.embedding_sqlurl = "postgresql" + p_config.embedding_sqlurl[18:]
    if "postgresql" not in p_config.embedding_sqlurl:
        raise TypeError("很抱歉，embedding sql 只支持 pgsql，或者，pr welcome。")
    if p_config.embedding_sqlurl :
        _async_embedding_database = await asyncpg.create_pool(p_config.embedding_sqlurl)
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
        )
        async with _async_database.begin() as conn:
            await conn.run_sync(metadata.create_all)
    except Exception as ex:
        print(ex)

    if p_config.pinecone_apikey:
        if not p_config.simpic_enable:
            raise Exception("呃啊，配置了 pinecone 就要开启simpic，因为这是绑定的")
        if not p_config.pinecone_environment:
            raise Exception("请配置 pinecone_environment")
        pinecone.init(
            api_key=p_config.pinecone_apikey, environment=p_config.pinecone_environment
        )
        if p_config.pinecone_index not in pinecone.list_indexes():
            pinecone.create_index(p_config.pinecone_index, dimension=384)
        if not _pincone_index:
            _pincone_index = pinecone.Index(p_config.pinecone_index)


@gdriver.on_startup
async def _():
    if not p_config.savepic_sqlurl:
        raise Exception("请配置 savepic_sqlurl")

    await init_db()

import numpy as np
import asyncpg

from typing import Optional
from nonebot import get_driver, logger

from .types import PicData
from .error import (
    SameNameException,
    NoPictureException,
    PermissionException,
    SimilarPictureException,
)
from .utils import word2vec
from ..config import plugin_config


gdriver = get_driver()
POOL: Optional[asyncpg.Pool] = None
POOL_LOCAL: asyncpg.Pool
"""没啥特别的，单纯是订阅/发布模式用来加速读取的，不涉及 vec 的原子读操作理论上是走这个。"""


@gdriver.on_startup
async def _():
    if not plugin_config.savepic_sqlurl:
        raise Exception("请配置 savepic_sqlurl")

    await init_db()


@gdriver.on_shutdown
async def _():
    global POOL
    if POOL:
        await POOL.close()


async def select_pic(filename: str, scope: str, strict: bool = False) -> Optional[str]:
    """根据名字和作用域查询图片 URL

    Parameters
    ----------
    filename: str
        图片名字
    scope: str
        作用域

    Returns
    -------
    Optional[str]
        图片 URL 或 None
    """

    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用查询功能")
        return None

    async with POOL_LOCAL.acquire() as conn:
        ret = await conn.fetchval(
            "SELECT url FROM picdata WHERE name = $1 AND scope @> ARRAY[$2] LIMIT 1;",
            filename,
            scope,
        )
        if ret or strict:
            return ret
        return await conn.fetchval(
            "SELECT url FROM picdata WHERE name = $1 AND scope @> ARRAY['globe'] LIMIT 1;",
            filename,
        )


async def savepic(
    filename: str,
    url: str,
    scope: str = "globe",
    uploader: str = "unknown",
    vec: Optional[np.ndarray] = None,
    collision_allow: bool = False,
) -> Optional[str]:
    """保存图片

    Parameters
    ----------
    filename: str
        图片名字
    url: str
        图片 URL
    scope: str
        作用域
    vec: Optional[np.ndarray]
        图片向量
    collision_allow: bool
        是否允许相似图片存在

    Returns
    -------
    Optional[str]
        如果是相同 URL 的图片，返回已存在的图片名字，否则返回 None

    Exceptions
    ----------
    SameNameException
        图片名字已存在

    SimilarPictureException
        存在相似图片
    """

    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用保存功能")
        return

    async with POOL.acquire() as conn:
        # 判断是否存在相同名字的图片
        ret = await conn.fetchval(
            "SELECT url FROM picdata WHERE name = $1 AND scope @> ARRAY[$2];",
            filename,
            scope,
        )
        if ret:
            raise SameNameException(filename, scope)

        # 如果 URL 已经存在，且对应图片名字不为空，则相似图片错误
        name = await conn.fetchval(
            "SELECT name FROM picdata WHERE url = $1 AND scope && ARRAY[$2, 'globe'];",
            url,
            scope,
        )
        if name:
            raise SimilarPictureException(name, float("inf"), url)

        # 从向量检索相似图片
        if not collision_allow and vec is not None:
            row = await conn.fetchrow(
                (
                    "SELECT name, url, (1-(vec <=> $1::halfvec)) AS similarity FROM picdata "
                    "WHERE vec IS NOT NULL AND (scope && ARRAY[$2, 'globe']::text[]) "
                    "AND (1-(vec <=> $1::halfvec)) >= 0.6 "
                    "ORDER BY similarity DESC LIMIT 1;"
                ),
                str(vec.tolist()),
                scope,
            )
            if row and row["similarity"] >= 0.75:
                raise SimilarPictureException(
                    row["name"], row["similarity"], row["url"]
                )

        # 事务
        async with conn.transaction():
            row = await conn.fetchrow(
                """
INSERT INTO picdata (name, scope, url, vec, uploader)
VALUES ($1, ARRAY[$2]::text[], $3, $4::halfvec, $5)
ON CONFLICT (url) DO UPDATE
SET
    scope = CASE
            WHEN EXCLUDED.scope = ARRAY['globe']::text[]
                THEN ARRAY['globe']::text[]
            WHEN NOT (picdata.scope @> EXCLUDED.scope)
                THEN array_append(picdata.scope, EXCLUDED.scope[1])
            ELSE picdata.scope
            END,
    vec   = COALESCE(EXCLUDED.vec, picdata.vec)
RETURNING name;""",
                filename,  # $1: 传入的 name
                scope,  # $2
                url,  # $3
                (str(vec.tolist()) if vec is not None else None),  # $4
                uploader,  # $5
            )

            if row["name"] != filename:
                return row["name"]


async def simpic(
    img_vec: np.ndarray, scope: str = "globe"
) -> tuple[float, Optional[PicData]]:
    """检索相似图片

    Parameters
    ----------
    img_vec : np.ndarray
        图片向量
    scope : str
        检索范围
    ignore_min : bool
        是否忽略最小相似度

    Returns
    -------
    Optional[float], Optional[PicData]
        相似度和图片数据
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用相似图片功能")
        return 0, None

    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            (
                "SELECT (1-(vec <=> $1::halfvec)) AS similarity, name, url FROM picdata "
                "WHERE vec IS NOT NULL AND (scope && ARRAY[$2, 'globe']::text[]) "
                "ORDER BY similarity DESC LIMIT 1;"
            ),
            str(img_vec.tolist()),
            scope,
        )
        if row:
            return row["similarity"], PicData(
                name=row["name"],
                url=row["url"],
            )
        return 0, None


async def rename(
    ori: str,
    des: str,
    source_scope: str,
    dest_scope: str,
    is_admin: bool = False,
    vec: Optional[np.ndarray] = None,
):
    """重命名图片（包括修改作用域）

    Parameters
    ----------
    ori: str
        原图片名字
    des: str
        目标图片名字
    source_scope: str
        原图片作用域
    dest_scope: str
        目标图片作用域

    Exceptions
    ----------
    NoPictureException
        原图片不存在
    SameNameException
        目标图片名字已存在
    PermissionException
        没有权限修改图片名字
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用重命名功能")
        return

    async with POOL.acquire() as conn:
        # 判断目标名字是否存在
        if not await conn.fetchval(
            "SELECT 1 FROM picdata WHERE name = $1 AND scope @> ARRAY[$2];",
            ori,
            source_scope,
        ):
            raise NoPictureException(ori)

        # 如果域不只一个，且不是管理员权限，则不允许修改
        if (
            not is_admin
            and await conn.fetchval(
                "SELECT array_length(scope, 1) FROM picdata WHERE name = $1 AND scope @> ARRAY[$2];",
                ori,
                source_scope,
            )
            > 1
        ):
            raise PermissionException(ori, "图片存在所处域不止一个")

        # 判断目标名字是否存在
        if await conn.fetchval(
            "SELECT 1 FROM picdata WHERE name = $1 AND scope @> ARRAY[$2];",
            des,
            dest_scope,
        ):
            raise SameNameException(des, dest_scope)

        await conn.execute(
            "UPDATE picdata SET name = $1, scope = CASE "
            "  WHEN $3 = 'globe' THEN ARRAY['globe']::text[] "
            "  WHEN scope @> ARRAY['globe'] THEN ARRAY[$3]::text[] "
            "  ELSE CASE "
            "    WHEN array_remove(scope, $4) @> ARRAY[$3] "
            "        THEN array_remove(scope, $4) "
            "    ELSE array_append(array_remove(scope, $4), $3) "
            "  END END, "
            "vec = CASE WHEN name <> $1 THEN $5 ELSE vec END "
            "WHERE name = $2 AND scope @> ARRAY[$4];",
            des,
            ori,
            dest_scope,
            source_scope,
            str(vec.tolist()) if vec is not None else None,
        )


async def delete(filename: str, scope: str):
    """删除图片

    Parameters
    ----------
    filename: str
        图片名字
    scope: str
        作用域

    Exceptions
    ----------
    NoPictureException
        图片不存在
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用删除功能")
        return

    async with POOL.acquire() as conn:
        if not await conn.fetchval(
            "SELECT 1 FROM picdata WHERE name = $1 AND scope @> ARRAY[$2];",
            filename,
            scope,
        ):
            raise NoPictureException(filename)
        await conn.execute(
            "DELETE FROM picdata WHERE name = $1 AND scope = ARRAY[$2]::text[];",
            filename,
            scope,
        )
        await conn.execute(
            "UPDATE picdata SET scope = array_remove(scope, $2) WHERE name = $1 AND scope @> ARRAY[$2];",
            filename,
            scope,
        )


async def randpic(
    name: str, scope: str = "globe", vector: bool = False
) -> tuple[PicData | None, str]:
    name = name.strip().replace("%", r"\%").replace("_", r"\_")
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用查询功能")
        return None, ""

    # 优先从只读连接池查询
    async with POOL_LOCAL.acquire() as conn:
        if not name:
            row = await conn.fetchrow(
                (
                    "SELECT name, scope, url FROM picdata "
                    "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                    "ORDER BY random() LIMIT 1;"
                ),
                scope,
            )
            if row:
                return (
                    PicData(
                        name=row["name"],
                        scope=row["scope"],
                        url=row["url"],
                    ),
                    "",
                )
            return None, ""
        row = await conn.fetchrow(
            (
                "SELECT name, scope, url FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                "AND name ILIKE $2 "
                "ORDER BY random() LIMIT 1;"
            ),
            scope,
            f"%{name}%",
        )
        if row:
            return (
                PicData(
                    name=row["name"],
                    scope=row["scope"],
                    url=row["url"],
                ),
                "",
            )

    if not vector:
        return None, ""
    v = await word2vec(name)
    if v is None:
        return None, ""

    # 如果没有找到，且需要向量检索，则进行向量检索
    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            (
                "SELECT name, scope, url, (1-(vec <=> $2::halfvec)) as similarity FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                "AND vec IS NOT NULL ORDER BY similarity DESC LIMIT 1;"
            ),
            scope,
            str(v.tolist()),
        )
        if row:
            return (
                PicData(
                    name=row["name"],
                    scope=row["scope"],
                    url=row["url"],
                ),
                f"（语义相似度检索，{row['similarity'] * 100:.2f}%）",
            )
    return None, ""


async def regexp_pic(reg: str, scope: str = "globe") -> Optional[PicData]:
    """根据正则表达式随机查询一张图片

    Parameters
    ----------
    reg: str
        正则表达式
    scope: str
        作用域

    Returns
    -------
    Optional[PicData]
        图片数据或 None
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用查询功能")
        return None
    reg = reg.strip()
    if not reg:
        reg = ".*"

    async with POOL_LOCAL.acquire() as conn:
        row = await conn.fetchrow(
            (
                "SELECT name, scope, url FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                "AND name ~* $2 "
                "ORDER BY random() LIMIT 1;"
            ),
            scope,
            reg,
        )
        if row:
            return PicData(
                name=row["name"],
                scope=row["scope"],
                url=row["url"],
            )


async def countpic(reg: str, scope: str = "globe") -> int:
    """
    统计图片数量

    Parameters
    ----------
    reg: str
        正则表达式
    scope: str
        作用域

    Returns
    -------
    int
        图片数量
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用统计功能")
        return 0

    reg = reg.strip()
    if not reg:
        reg = ".*"

    async with POOL_LOCAL.acquire() as conn:
        return (
            await conn.fetchval(
                (
                    "SELECT COUNT(*) FROM picdata "
                    "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                    "AND name ~* $2;"
                ),
                scope,
                reg,
            )
            or 0
        )


async def listpic(
    reg: str, scope: str = "globe", pages: int = 0
) -> list[tuple[str, bool]]:
    """
    列出图片

    Parameters
    ----------
    reg: str
        正则表达式
    scope: str
        作用域
    pages: int
        页码

    Returns
    -------
    list[tuple[str, bool]]
        (图片名, 是否为全局) 列表
    """

    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用统计功能")
        return []

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

    async with POOL_LOCAL.acquire() as conn:
        row = await conn.fetch(
            (
                "SELECT name, (scope @> ARRAY['globe']) AS is_global FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) "
                "AND name ~* $2 ORDER BY name OFFSET $3 LIMIT $4;"
            ),
            scope,
            reg,
            pages * plugin_config.count_per_page_in_list,
            _count,
        )
        if row:
            return [(r["name"], r["is_global"]) for r in row]
        return []


async def check_uploader(filename: str, scope: str, uploader: str) -> bool:
    """获取图片上传者

    Parameters
    ----------
    filename: str
        图片名字
    scope: str
        作用域
    uploader: str
        上传者

    Returns
    -------
    Optional[str]
        上传者，可能为 None
    """
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用查询功能")
        return False

    async with POOL_LOCAL.acquire() as conn:
        return bool(
            await conn.fetchval(
                "SELECT 1 FROM picdata WHERE name = $1 AND scope @> ARRAY[$2] AND uploader = $3;",
                filename,
                scope,
                uploader,
            )
        )


async def init_db():
    global POOL, POOL_LOCAL
    POOL = await asyncpg.create_pool(
        plugin_config.savepic_sqlurl,
        min_size=1,
        max_size=10,
        timeout=60,
        max_inactive_connection_lifetime=300,
    )
    if plugin_config.cache_sqlurl:
        POOL_LOCAL = await asyncpg.create_pool(
            plugin_config.cache_sqlurl,
            min_size=1,
            max_size=10,
            timeout=60,
            max_inactive_connection_lifetime=300,
        )
    else:
        POOL_LOCAL = POOL

    async def create_table(pool: asyncpg.Pool):
        async with pool.acquire() as conn:
            # 判断是否存在表
            if await conn.fetchval(
                "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'picdata');"
            ):
                logger.info("picdata 表已存在，跳过创建")
                return
            async with conn.transaction():
                # 启用插件
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                logger.info("已启用 pg_trgm 和 vector 扩展")

                # 创建表
                await conn.execute(
                    (
                        "CREATE TABLE picdata (\n"
                        "  name     text   NOT NULL, \n"
                        "  scope    text[] NOT NULL, \n"
                        "  url      text   PRIMARY KEY, \n"
                        "  vec      halfvec(2048), \n"
                        "  uploader text   NOT NULL, \n"
                        ");"
                    )
                )
                logger.info("已创建 picdata 表")

                # 创建索引
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS picdata_name_lower_btree ON picdata (lower(name)); \n"
                    "CREATE INDEX IF NOT EXISTS picdata_name_trgm ON picdata USING GIN (lower(name) gin_trgm_ops); \n"
                    "CREATE INDEX IF NOT EXISTS picdata_scope_gin ON picdata USING GIN (scope); \n"
                    "CREATE INDEX IF NOT EXISTS picdata_vec_hnsw_ip ON picdata USING hnsw (vec halfvec_ip_ops) WITH (m = 16, ef_construction = 64);"
                )
                logger.info("已创建 picdata 表的索引")

    await create_table(POOL)

    # 判断只读池是否有表 picdata，没有则改用主池
    if POOL_LOCAL is not POOL:
        async with POOL_LOCAL.acquire() as conn:
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'picdata');"
            ):
                logger.warning(
                    "只读连接池中不存在 picdata 表，改用主连接池作为只读连接池"
                )
                POOL_LOCAL = POOL

    if POOL_LOCAL is not POOL:
        logger.info("使用了独立的只读连接池，请确保设定了数据库的同步复制。")

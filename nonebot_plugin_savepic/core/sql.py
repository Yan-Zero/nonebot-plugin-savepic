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


async def select_pic(filename: str, scope: str) -> Optional[str]:
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

    async with POOL.acquire() as conn:
        ret = await conn.fetchval(
            "SELECT COALESCE("
            "  (SELECT url FROM picdata "
            "    WHERE name = $1 AND $2 = ANY(scope) "
            "    ORDER BY id DESC LIMIT 1),"
            "  (SELECT url FROM picdata "
            "    WHERE name = $1 AND 'globe' = ANY(scope) "
            "    ORDER BY id DESC LIMIT 1)"
            ");",
            filename,
            scope,
        )
        return ret


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
            "SELECT id FROM picdata WHERE name = $1 AND $2 = ANY(scope);",
            filename,
            scope,
        )
        if ret:
            raise SameNameException(filename, scope)

        # 如果 URL 已经存在，且对应图片名字不为空，则相似图片错误
        name = await conn.fetchval(
            "SELECT name FROM picdata WHERE url = $1 AND name <> '' AND $2 = ANY(scope);",
            url,
            scope,
        )
        if name:
            raise SimilarPictureException(name, 1.0, url)

        # 从向量检索相似图片
        if not collision_allow and vec is not None:
            row = await conn.fetchrow(
                (
                    "SELECT name, url, - (vec16 <#> ($1::halfvec) AS similarity "
                    "FROM picdata "
                    "WHERE vec IS NOT NULL AND (scope && ARRAY[$2, 'globe']::text[]) AND name <> '' "
                    "ORDER BY vec16 <#> $1::halfvec LIMIT 1;"
                ),
                vec.astype(np.float16).tolist(),
                scope,
            )
            if row and row["similarity"] >= 0.925:
                raise SimilarPictureException(
                    row["name"], row["similarity"], row["url"]
                )

        sql = """WITH 
take AS (
  SELECT ctid
  FROM picdata
  WHERE name = ''
  FOR UPDATE SKIP LOCKED
  LIMIT 1
),
upd_empty AS (
  UPDATE picdata p
  SET name     = $1,
      scope    = ARRAY[$2]::text[],
      url      = $3,
      vec      = $4::halfvec
      uploader = $5
  FROM take t
  WHERE p.ctid = t.ctid
    AND NOT EXISTS (SELECT 1 FROM picdata q WHERE q.url = $3)
  RETURNING p.name
),
ins AS (
  INSERT INTO picdata (name, scope, url, vec, uploader)
  SELECT $1, ARRAY[$2]::text[], $3, $4::halfvec, $5
  WHERE NOT EXISTS (SELECT 1 FROM upd_empty)
  ON CONFLICT (url) DO UPDATE
  SET
    name     = CASE WHEN picdata.name = '' THEN EXCLUDED.name ELSE picdata.name END,
    scope    = CASE
                  WHEN picdata.name = '' THEN EXCLUDED.scope
                  WHEN EXCLUDED.scope = ARRAY['globe']::text[] THEN ARRAY['globe']::text[]
                  WHEN NOT (EXCLUDED.scope[1] = ANY(picdata.scope)) THEN array_append(picdata.scope, EXCLUDED.scope[1])
                  ELSE picdata.scope
               END,
    vec      = COALESCE(EXCLUDED.vec, picdata.vec)
    uploader = EXCLUDED.uploader
  RETURNING picdata.name
)

SELECT name FROM upd_empty
UNION ALL
SELECT name FROM ins
LIMIT 1;"""
        # 事务
        async with conn.transaction():
            ret = await conn.fetchval(
                sql,
                filename,
                scope,
                url,
                vec.astype(np.float16).tolist() if vec is not None else None,
                uploader,
            )
            if filename != name:
                return name


async def simpic(
    img_vec: np.ndarray, scope: str = "globe", ignore_min: bool = False
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
                "SELECT id, 1 - (vec <=> $1::halfvec) AS similarity, name, url "
                "FROM picdata "
                "WHERE vec IS NOT NULL AND (scope && ARRAY[$2, 'globe']::text[]) "
                "AND name <> '' "
                + ("" if ignore_min else "and vec <=> $1::halfvec < 0.35 ")
                + "ORDER BY similarity DESC LIMIT 1;"
            ),
            str(img_vec.astype(np.float16).tolist()),
            scope,
        )
        if row:
            return row["similarity"], PicData(
                id=row["id"],
                name=row["name"],
                url=row["url"],
            )
        return 0, None


async def rename(
    ori: str, des: str, source_scope: str, dest_scope: str, is_admin: bool = False
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
            "SELECT 1 FROM picdata WHERE name = $1 AND $2 = ANY(scope);",
            ori,
            source_scope,
        ):
            raise NoPictureException(ori)

        # 如果域不只一个，且不是管理员权限，则不允许修改
        if (
            not is_admin
            and await conn.fetchval(
                "SELECT array_length(scope, 1) FROM picdata WHERE name = $1 AND $2 = ANY(scope);",
                ori,
                source_scope,
            )
            > 1
        ):
            raise PermissionException(ori, "图片存在所处域不止一个")

        # 判断目标名字是否存在
        if await conn.fetchval(
            "SELECT 1 FROM picdata WHERE name = $1 AND $2 = ANY(scope);",
            des,
            dest_scope,
        ):
            raise SameNameException(des, dest_scope)

        await conn.execute(
            "UPDATE picdata SET name = $1, scope = CASE "
            "WHEN $3 = 'globe' THEN ARRAY['globe']::text[] "
            "WHEN 'globe' = ANY(scope) AND $4 <> 'globe' THEN ARRAY[$4]::text[] "
            "ELSE scope END, vec = CASE WHEN name <> $1 THEN NULL ELSE vec END "
            "WHERE name = $2 AND $3 = ANY(scope);",
            des,
            ori,
            source_scope,
            dest_scope,
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
            "SELECT 1 FROM picdata WHERE name = $1 AND $2 = ANY(scope);",
            filename,
            scope,
        ):
            raise NoPictureException(filename)

        await conn.execute(
            "UPDATE picdata SET name = CASE WHEN scope = ARRAY[$2]::text[] THEN '' ELSE name END, "
            "scope = CASE WHEN scope = ARRAY[$2]::text[] THEN scope ELSE array_remove(scope, $2) END "
            "WHERE name = $1 AND $2 = ANY(scope);",
            filename,
            scope,
        )


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

    async with POOL.acquire() as conn:
        row = await conn.fetchrow(
            (
                "SELECT id, name, scope, url FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
                "AND name ~* $2 "
                "ORDER BY random() LIMIT 1;"
            ),
            scope,
            reg,
        )
        if row:
            return PicData(
                id=row["id"],
                name=row["name"],
                scope=row["scope"],
                url=row["url"],
            )


async def randpic(
    name: str, scope: str = "globe", vector: bool = False, threshold: float = 0.45
) -> tuple[PicData | None, str]:
    name = name.strip().replace("%", r"\%").replace("_", r"\_")
    if not POOL:
        logger.warning("未配置 savepic_sqlurl，无法使用查询功能")
        return None, ""
    async with POOL.acquire() as conn:
        if not name:
            row = await conn.fetchrow(
                (
                    "SELECT id, name, scope, url FROM picdata "
                    "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
                    "ORDER BY random() LIMIT 1;"
                ),
                scope,
            )
            if row:
                return (
                    PicData(
                        id=row["id"],
                        name=row["name"],
                        scope=row["scope"],
                        url=row["url"],
                    ),
                    "",
                )
            return None, ""
        row = await conn.fetchrow(
            (
                "SELECT id, name, scope, url FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
                "AND name ILIKE $2 "
                "ORDER BY random() LIMIT 1;"
            ),
            scope,
            f"%{name}%",
        )
        if row:
            return (
                PicData(
                    id=row["id"],
                    name=row["name"],
                    scope=row["scope"],
                    url=row["url"],
                ),
                "",
            )

        if not vector:
            return None, ""

        row = await conn.fetchrow(
            (
                "SELECT id, name, scope, url FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
                "AND vec IS NOT NULL AND vec <=> $2::halfvec <= $3::float "
                "ORDER BY vec <#> $2::halfvec LIMIT 1;"
            ),
            scope,
            str((await word2vec(name)).tolist()),
            threshold,
        )
        if row:
            return (
                PicData(
                    id=row["id"],
                    name=row["name"],
                    scope=row["scope"],
                    url=row["url"],
                ),
                "（语义向量相似度检索）",
            )
    return None, ""


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

    async with POOL.acquire() as conn:
        return (
            await conn.fetchval(
                (
                    "SELECT COUNT(*) FROM picdata "
                    "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
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

    async with POOL.acquire() as conn:
        row = await conn.fetch(
            (
                "SELECT name, ('globe' = ANY(scope)) AS is_global FROM picdata "
                "WHERE (scope && ARRAY[$1, 'globe']::text[]) AND name <> '' "
                "AND name ~* $2 "
                "ORDER BY name "
                "OFFSET $3 LIMIT $4;"
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

    async with POOL.acquire() as conn:
        return bool(
            await conn.fetchval(
                "SELECT 1 FROM picdata WHERE name = $1 AND $2 = ANY(scope) AND uploader = $3;",
                filename,
                scope,
                uploader,
            )
        )


async def init_db():
    global POOL
    POOL = await asyncpg.create_pool(
        plugin_config.savepic_sqlurl,
        min_size=1,
        max_size=10,
        timeout=60,
        max_inactive_connection_lifetime=300,
    )

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
                        "  id       bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, \n"
                        "  name     text   NOT NULL, \n"
                        "  scope    text[] NOT NULL, \n"
                        "  url      text   NOT NULL, \n"
                        "  vec      halfvec(2048), \n"
                        "  uploader text   NOT NULL, \n"
                        "  CONSTRAINT unique_url UNIQUE (url) NOT DEFERRABLE \n"
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

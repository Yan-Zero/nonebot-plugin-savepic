import httpx
import numpy as np

from io import BytesIO
from pathlib import Path
from nonebot.log import logger

from ..config import plugin_config


MEAN_VECTOR = None

if plugin_config.normalize_vector and Path(plugin_config.normalize_vector).exists():
    with open(plugin_config.normalize_vector, "r") as f:
        # 读取均值向量，是list[float]
        _ = f.read().strip()
        if _.startswith("[") and _.endswith("]"):
            _ = _[1:-1]
        MEAN_VECTOR = np.array([float(x) for x in _.split(",")])
        logger.info(f"Loaded mean vector from {plugin_config.normalize_vector}")


async def word2vec(word: str) -> np.ndarray | None:
    if not word:
        return None
    async with httpx.AsyncClient() as client:
        try:
            rsp = await client.post(
                plugin_config.embedding_url,
                json={
                    "model": plugin_config.embedding_model,
                    "input": [
                        {
                            "type": "text",
                            "text": word,
                        }
                    ],
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {plugin_config.embedding_key}",
                },
            )
            rsp.raise_for_status()
            data = rsp.json()
        except Exception as e:
            logger.warning(f"Network seems down, cannot access internet: {e}")
            return None
    try:
        ret = np.array(data["data"]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding word: {word}, {e}")
        return None
    if MEAN_VECTOR is not None and len(MEAN_VECTOR) == len(ret):
        ret = ret - MEAN_VECTOR
        # 归一化
        ret = ret / np.linalg.norm(ret)
    return ret


async def img2vec(img: str, title: str = "") -> np.ndarray | None:
    # img 转为 base64 url，获取mime类型
    input = []
    if title:
        input.append(
            {
                "type": "text",
                "text": f"Title of the image: {title}",
            }
        )
    if img.startswith("http"):
        input.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": img,
                },
            }
        )
    else:
        raise ValueError("img must be a valid URL string")
    async with httpx.AsyncClient() as client:
        try:
            rsp = await client.post(
                plugin_config.embedding_url,
                json={
                    "model": plugin_config.embedding_model,
                    "input": input,
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {plugin_config.embedding_key}",
                },
            )
            rsp.raise_for_status()
            data = rsp.json()
        except Exception as e:
            logger.warning(f"Network seems down, cannot access internet: {e}")
            return None
    try:
        ret = np.array(data["data"]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding image: {title}, {e}")
        return None
    if MEAN_VECTOR is not None and len(MEAN_VECTOR) == len(ret):
        ret = ret - MEAN_VECTOR
        # 归一化
        ret = ret / np.linalg.norm(ret)
    return ret


async def upload_image(
    img: bytes | Path | str, filename: str = "image.png"
) -> str | None:
    """上传图片到图床，返回图片URL"""
    if isinstance(img, Path):
        if not img.exists():
            return None
        img = img.read_bytes()
    elif isinstance(img, str):
        if img.startswith("http"):
            return img
        p = Path(img)
        if not p.exists():
            return None
        img = p.read_bytes()
    files = {"file": (filename, BytesIO(img), "application/octet-stream")}
    async with httpx.AsyncClient() as client:
        try:
            rsp = await client.post("https://tmpfiles.org/api/v1/upload", files=files)
            rsp.raise_for_status()
            data = rsp.json()
            logger.info(f"Uploaded image to {data}")
            return data["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")
        except Exception as e:
            logger.warning(f"Network seems down, cannot access internet: {e}")
            return None

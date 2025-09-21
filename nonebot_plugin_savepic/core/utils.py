import httpx
import numpy as np

from nonebot.log import logger

from ..config import plugin_config


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
        return np.array(data["data"]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding word: {word}, {e}")
        return None


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
        return np.array(data["data"]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding image: {title}, {e}")
        return None

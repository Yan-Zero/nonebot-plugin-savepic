import numpy as np
import httpx
import base64
import imghdr
from nonebot.log import logger

from ..config import plugin_config

NULL_EMB: np.ndarray = np.zeros(2048)


async def word2vec(word: str) -> np.ndarray:
    if not word:
        return NULL_EMB
    async with httpx.AsyncClient() as client:
        try:
            rsp = await client.post(
                plugin_config.embedding_url,
                json={
                    "model": plugin_config.embedding_model,
                    "input": {
                        "type": "text",
                        "text": word,
                    },
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
            return NULL_EMB
    try:
        return np.array(data["data"][0]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding word: {word}, {e}")
        return NULL_EMB


async def img2vec(img: bytes, title: str = "") -> np.ndarray | None:
    # img 转为 base64 url，获取mime类型
    mime = imghdr.what(None, h=img)
    if not mime:
        logger.error("Cannot recognize image type")
        return NULL_EMB
    input = []
    if title:
        input.append(
            {
                "type": "text",
                "text": f"Title of the image: {title}",
            }
        )
    input.append(
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{base64.b64encode(img).decode()}"
            },
        }
    )
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
            return NULL_EMB
    try:
        return np.array(data["data"][0]["embedding"])
    except Exception as e:
        logger.error(f"Error while embedding image: {title}, {e}")
        return NULL_EMB

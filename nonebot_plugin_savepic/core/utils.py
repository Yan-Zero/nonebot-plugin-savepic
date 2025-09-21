import numpy as np
import base64
import imghdr
import openai

from nonebot.log import logger

from ..config import plugin_config

CLIENT = openai.AsyncOpenAI(
    api_key=plugin_config.embedding_key,
    base_url=plugin_config.embedding_baseurl,
)
NULL_EMB: np.ndarray = np.zeros(2048)


async def word2vec(word: str) -> np.ndarray:
    if not word:
        return NULL_EMB
    try:
        return np.array(
            (
                await CLIENT.embeddings.create(
                    input=word, model=plugin_config.embedding_model
                )
            )
            .data[0]
            .embedding
        )
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
    try:
        return np.array(
            (
                await CLIENT.embeddings.create(
                    input=input, model=plugin_config.embedding_model
                )
            )
            .data[0]
            .embedding
        )
    except Exception as e:
        logger.error(f"Error while embedding image: {title}, {e}")
        return NULL_EMB

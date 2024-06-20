import nonebot
import httpx
import hashlib
import os
from PIL import Image
from nonebot import get_plugin_config
from .config import Config

if False:
    from .model import EmoSame

_emo_same = None
_httpx_async = None
gdriver = nonebot.get_driver()
plugin_config = get_plugin_config(Config)


def del_pic(url: str):
    if url.startswith("http"):
        return
    if os.path.exists(url):
        os.remove(url)


async def load_pic(url: str) -> bytes:
    global _httpx_async
    if url.startswith("http"):
        if not _httpx_async:
            _httpx_async = httpx.AsyncClient()
        resp = await _httpx_async.get(url)
        resp.raise_for_status()
        return resp.content
    if os.path.exists(url):
        with open(url, "rb") as f:
            return f.read()
    raise Exception(f"不支持的 URL\n{url}")


async def write_pic(url: str, des_dir: str = None) -> str:
    if not des_dir:
        des_dir = "savepic"
    if not os.path.exists(des_dir):
        os.makedirs(des_dir)

    byte = await load_pic(url)
    filename = hashlib.sha256(byte).hexdigest()
    while os.path.exists(os.path.join(des_dir, filename)):
        filename += "_"
    with open(os.path.join(des_dir, filename), "wb") as f:
        f.write(byte)
    return os.path.join(des_dir, filename)

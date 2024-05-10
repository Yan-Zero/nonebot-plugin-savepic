import nonebot
import httpx
import hashlib
import os
from PIL import Image
from .config import Config

if False:
    from .model import EmoSame

_emo_same = None
_httpx_async = None
gdriver = nonebot.get_driver()
plugin_config = Config.parse_obj(gdriver.config)


def remove_alpha(im: Image) -> Image:
    # Only process if image has transparency (http://stackoverflow.com/a/1963146)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        # Need to convert to RGBA if LA format due to a bug in PIL (http://stackoverflow.com/a/1963146)
        alpha = im.convert("RGBA").split()[-1]

        # Create a new background image of our matt color.
        # Must be RGBA because paste requires both images have the same format
        # (http://stackoverflow.com/a/8720632  and  http://stackoverflow.com/a/9459208)
        bg = Image.new("RGBA", im.size, (255, 255, 255) + (255,))
        bg.paste(im, mask=alpha)
        return bg

    else:
        return im


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


@gdriver.on_startup
async def _():
    global _emo_same, plugin_config
    if not plugin_config.simpic_enable:  # AI 相似度判断
        return

    # if not _emo_same:
    #     _emo_same = EmoSame(plugin_config.p_model_path, plugin_config.q_model_path)

import scipy.fftpack as fft
import numpy as np
import httpx
import os
from PIL import Image
from io import BytesIO

_httpx_async = None


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
    raise Exception("不支持的 URL")


def p_hash(img: bytes) -> bytes:
    pic = remove_alpha(
        Image.open(BytesIO(img)).resize((128, 128), Image.Resampling.LANCZOS)
    ).convert("L")
    dct = fft.dct(np.array(pic))
    average = np.median(dct)
    return np.packbits(dct[:16, :16] > average).tobytes()

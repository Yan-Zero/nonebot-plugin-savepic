import hashlib
import pathlib

import httpx

from .error import SamePictureHashException


def del_pic(url: str | pathlib.Path):
    if url.startswith("http"):
        return
    if isinstance(url, str):
        _ = pathlib.Path(url)
    else:
        _ = url
    if _.exists():
        _.unlink()


async def load_pic(url: str) -> bytes:
    if url.startswith("http"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    if pathlib.Path(url).exists():
        with open(url, "rb") as f:
            return f.read()
    raise Exception(f"不支持的 URL\n{url}")


async def write_pic(url: str, des_dir: str = None) -> str:
    if not des_dir:
        des_dir = "savepic"
    path = pathlib.Path(des_dir)
    path.mkdir(parents=True, exist_ok=True)

    byte = await load_pic(url)
    file = path / hashlib.sha256(byte).hexdigest()
    if file.exists():
        raise SamePictureHashException(file.name, url)
    with open(file, "wb") as f:
        f.write(byte)
    return file.as_posix()

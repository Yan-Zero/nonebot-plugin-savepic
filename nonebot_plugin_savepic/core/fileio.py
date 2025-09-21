import httpx
import hashlib
import pathlib


async def del_pic(url: str | pathlib.Path):
    if isinstance(url, pathlib.Path):
        url = url.as_posix()
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


async def write_pic(url: str, des_dir: str | None = None) -> str:
    if not des_dir:
        des_dir = "savepic"
    path = pathlib.Path(des_dir)
    path.mkdir(parents=True, exist_ok=True)

    byte = await load_pic(url)
    file = path / hashlib.sha256(byte).hexdigest()

    with open(file, "wb") as f:
        f.write(byte)
    return file.as_posix()

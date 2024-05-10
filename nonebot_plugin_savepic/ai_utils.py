import tempfile
import hashlib
import pathlib

from nonebot import get_plugin_config
from dashscope import MultiModalEmbedding
from dashscope import TextEmbedding
from http import HTTPStatus

from .config import Config
from .picture import _emo_same


plugin_config = get_plugin_config(Config)


def file2vec(path: pathlib.Path, title: str = None) -> list:
    input = [
        {
            "factor": 5,
            "image": path.absolute().as_uri(),
        },
    ]
    if title:
        input.append(
            {
                "factor": 1,
                "text": title,
            },
        )
    resp = MultiModalEmbedding.call(
        model=MultiModalEmbedding.Models.multimodal_embedding_one_peace_v1,
        input=input,
        auto_truncation=True,
    )
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError("Dashscope API Error")
    return resp.output["embedding"]


def img2vec(img: bytes, title: str = None) -> list:
    """1536 D"""
    return None

    if plugin_config.simpic_model.lower() == "one-peach":
        path = pathlib.Path(tempfile.gettempdir) / "img2vec"
        if not path.exists():
            path.mkdir()
        path /= hashlib.sha256(img).hexdigest() + ".png"
        with open(path, "wb+") as f:
            f.write(img)

        return file2vec(path=path, title=title)

    if not _emo_same:
        return None
    return _emo_same.quantify_tolist(img)


def word2vec(word: str) -> list[float]:
    resp = TextEmbedding.call(
        model=TextEmbedding.Models.text_embedding_v2, input=word, text_type="query"
    )
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError("Dashscope API Error")
    return resp.output["embeddings"][0]["embedding"]

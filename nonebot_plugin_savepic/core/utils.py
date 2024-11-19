import torch
from torchvision.transforms import transforms
from PIL import Image
from http import HTTPStatus
from nonebot import get_driver
from nonebot.log import logger
from dashscope import TextEmbedding
from io import BytesIO
from .model import ViTnLPE
from ..config import p_config

img_model = None


@get_driver().on_startup
async def _():
    global img_model
    if img_model:
        return
    img_model = ViTnLPE(
        heads=16,
        input_resolution=224,
        layers=24,
        output_dim=1024,
        patch_size=14,
        width=1024,
    )
    img_model.load_state_dict(
        torch.load(
            p_config.p_model_path,
            map_location=torch.device("cpu"),
            weights_only=True,
        )
    )
    img_model.to(torch.bfloat16)
    img_model.eval()
    logger.info(
        "ViTnLPE model loaded, input resolution: 224x224, patch size: 14x14, width: 1024, heads: 16, layers: 24, output dim: 1024"
    )


__t = transforms.Compose(
    [
        lambda x: x.convert("RGB"),
        transforms.Resize((224, 224), transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize(
            (0.48145466, 0.4578275, 0.40821073),
            (0.26862954, 0.26130258, 0.27577711),
        ),
    ]
)


def img2vec(img: bytes, title: str = None) -> list | None:
    """1024 D"""
    global p_config, __t, img_model
    if not p_config.simpic_model:
        return None
    if p_config.simpic_model not in ["ViT/16"]:
        raise NotImplementedError(f"Unsupported model: {p_config.simpic_model}")
    return img_model(
        __t(Image.open(BytesIO(img))).to(torch.bfloat16).unsqueeze(0)
    ).tolist()


def word2vec(word: str) -> list[float]:
    resp = TextEmbedding.call(
        model=TextEmbedding.Models.text_embedding_v2, input=word, text_type="query"
    )
    if resp.status_code != HTTPStatus.OK:
        raise RuntimeError("Dashscope API Error")
    return resp.output["embeddings"][0]["embedding"]

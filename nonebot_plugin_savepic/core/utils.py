import torch
import asyncio
import numpy as np
import openai
import base64
import json
from torchvision.transforms import transforms
from PIL import Image
from nonebot import get_driver
from nonebot.log import logger
from io import BytesIO
from .model import ViTnLPE
from ..config import p_config

img_model = None
CLIENT = openai.AsyncOpenAI(
    api_key=p_config.openai_apikey, base_url=p_config.openai_baseurl
)


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


async def word2vec(word: str) -> list[float]:
    return (
        (await CLIENT.embeddings.create(input=word, model=p_config.embedding_model))
        .data[0]
        .embedding
    )


async def img2vec(img: bytes, title: str = "") -> list | None:
    """1024 D"""
    global p_config, __t, img_model
    if not p_config.simpic_model:
        return None
    if p_config.simpic_model not in ["ViT/16-Bfloat16-Modify"]:
        raise NotImplementedError(f"Unsupported model: {p_config.simpic_model}")
    return (
        await asyncio.to_thread(
            img_model,
            __t(Image.open(BytesIO(img))).to(torch.bfloat16).unsqueeze(0),
            torch.Tensor(np.array(await word2vec(title)))
            .to(torch.bfloat16)
            .unsqueeze(0),
        )
    ).tolist()[0]


async def ocr(img: bytes) -> str:
    prompt = """Your response should be in the following format:
```
{
    "text": "The text detected in the image.",
    "score": "The confidence score of the text detection."
}

If the text detection fails, return an empty string.
```
{
    "text": "",
    "score": 0.0
}
```"""

    ret = (
        (
            await CLIENT.chat.completions.create(
                model=p_config.ocr_model,
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "OCR:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64.b64encode(img).decode()}"
                                },
                            },
                        ],
                    },
                ],
            )
        )
        .choices[0]
        .message.content
    )
    try:
        return json.loads(ret.split("```")[1].split("```")[0].strip("`").strip("json"))
    except Exception:
        logger.error(f"OCR error: {ret}")
        return {}

from io import BytesIO
from sqlalchemy import TEXT
from sqlalchemy import BOOLEAN
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_datastore import get_plugin_data

plugin_data = get_plugin_data()
plugin_data.use_global_registry()
Model = plugin_data.Model


class PicData(Model):
    """消息记录"""

    __tablename__ = "picdata"

    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(TEXT)
    """ 图片名称 """
    group: Mapped[str] = mapped_column(TEXT)
    """ 所属群组 id """
    url: Mapped[str] = mapped_column(TEXT)
    """ 图片目录 """
    u_vec_img: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    u_vec_text: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)


if False:
    import torch
    import numpy as np
    from PIL import Image
    from torchvision import transforms
    from networks.resnet_big import *
    from torch.quantization import get_default_qconfig
    from torch.quantization.quantize_fx import prepare_fx, convert_fx

    q_config = get_default_qconfig()
    qconfig_dict = {"": q_config}

    class EmoSame:
        def __init__(self, p_path, q_path):
            try:
                self.device = torch.device("cpu")
                float_model = torch.load(p_path, map_location="cpu")
                float_model.eval()

                p_model = prepare_fx(
                    float_model,
                    qconfig_dict,
                    example_inputs=torch.randn(1, 3, 224, 224),
                )

                self.model = convert_fx(p_model)
                self.model.load_state_dict(torch.load(q_path, map_location="cpu"))
                self.model = self.model.to(self.device)
                self.model.eval()

                self.normalize = transforms.Compose(
                    [
                        transforms.Resize((224, 224)),
                        transforms.ToTensor(),
                        transforms.Normalize(
                            mean=(0.5, 0.5, 0.5), std=(0.25, 0.25, 0.25)
                        ),
                    ]
                )
            except Exception as e:
                print("Failed to load model: {}".format(str(e)))

        def quantify_tolist(self, img: bytes) -> list:
            try:
                img = Image.open(BytesIO(img)).convert("RGB")
                background = Image.new("RGB", (224, 224), (255, 255, 255))
                width, height = img.size
                if width >= height:
                    new_width = 224
                    new_height = int(height * 224 / width)
                else:
                    new_height = 224
                    new_width = int(width * 224 / height)
                x_offset = (224 - new_width) // 2
                y_offset = (224 - new_height) // 2
                background.paste(
                    img.resize((new_width, new_height), Image.Resampling.LANCZOS),
                    (x_offset, y_offset),
                )

                im = self.normalize(background).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    return self.model(im).cpu().numpy().tolist()
            except Exception as e:
                print("Failed to quantify: {}".format(str(e)))
                return []

        def quantify(self, img_path: str) -> np.ndarray:
            try:
                im = (
                    self.normalize(Image.open(img_path).convert("RGB"))
                    .unsqueeze(0)
                    .to(self.device)
                )
                with torch.no_grad():
                    return self.model(im).cpu().numpy()
            except Exception as e:
                print("Failed to quantify: {}".format(str(e)))
                return np.array([])

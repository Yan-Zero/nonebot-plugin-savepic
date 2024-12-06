from sqlalchemy import TEXT
from sqlalchemy import BOOLEAN
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

Model = declarative_base(name="Model")


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


class PicLife(Model):
    """图片生命周期"""

    __tablename__ = "piclife"

    __table_args__ = {"extend_existing": True}

    url: Mapped[str] = mapped_column(TEXT, primary_key=True)
    """ 图片目录 """
    life: Mapped[int] = mapped_column(BOOLEAN, nullable=False, default=0)
    """ 图片生命周期 """

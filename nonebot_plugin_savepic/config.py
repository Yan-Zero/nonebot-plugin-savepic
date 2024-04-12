from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""

    savepic_admin: list[str] = []
    savepic_dir: str = "savepic"
    savepic_sqlurl: str
    pinecone_apikey: str
    pinecone_index: str = "savepic"
    pinecone_environment: str
    simpic_enable: bool = False
    p_model_path: str = "networks/ckpt_epoch_100_rein.pth"
    q_model_path: str = "networks/ckpt_epoch_100_rein.pth.qt.pth"
    embedding_sqlurl: str
    dashscope_api: str
    black_group: list[str]

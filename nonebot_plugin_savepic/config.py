from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    """Plugin Config Here"""

    savepic_admin: list[str] = []
    savepic_dir: str = "savepic"
    savepic_sqlurl: str

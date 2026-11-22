import nonebot
import pytest
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN


def pytest_configure(config: pytest.Config) -> None:
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx+~websockets",
        "savepic_sqlurl": "postgresql://test/test",
        "embedding_key": "test",
        "embedding_url": "http://127.0.0.1/embedding",
        "embedding_model": "test",
    }
    # 不跑启动钩子，避免连接数据库
    config.stash[NONEBOT_START_LIFESPAN] = False


@pytest.fixture(scope="session", autouse=True)
def load_plugin(nonebug_init: None):
    from nonebot.adapters.milky import Adapter as MilkyAdapter
    from nonebot.adapters.onebot.v11 import Adapter as V11Adapter

    driver = nonebot.get_driver()
    driver.register_adapter(V11Adapter)
    driver.register_adapter(MilkyAdapter)
    nonebot.load_plugin("nonebot_plugin_savepic")

from typing import Optional

import pytest
from nonebug import App
from nonebot.adapters.milky import Adapter as MilkyAdapter
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky import Message as MilkyMsg
from nonebot.adapters.milky import MessageSegment as MilkySeg
from nonebot.adapters.milky.event import FriendMessageEvent as MilkyFME
from nonebot.adapters.milky.event import GroupMessageEvent as MilkyGME
from nonebot.adapters.milky.model.message import IncomingMessage
from nonebot.adapters.onebot.v11 import Adapter as V11Adapter
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from nonebot.adapters.onebot.v11 import Message as V11Msg
from nonebot.adapters.onebot.v11 import MessageSegment as V11Seg
from nonebot.adapters.onebot.v11.event import GroupMessageEvent as V11GME
from nonebot.adapters.onebot.v11.event import PrivateMessageEvent as V11PME
from nonebot.adapters.onebot.v11.event import Reply as V11Reply
from nonebot.adapters.onebot.v11.event import Sender

GROUP = 114514
USER = 1919810
SELF = 10001


def v11_event(text: str = "hi", group: bool = True, reply: Optional[V11Reply] = None):
    common = dict(
        time=0,
        self_id=SELF,
        post_type="message",
        sub_type="normal",
        user_id=USER,
        message_id=1,
        message=V11Msg(text),
        original_message=V11Msg(text),
        raw_message=text,
        font=0,
        sender=Sender(user_id=USER, nickname="u"),
        reply=reply,
    )
    if group:
        return V11GME(message_type="group", group_id=GROUP, **common)
    return V11PME(message_type="private", **common)


def milky_data(segments: list[dict], group: bool = True, seq: int = 1) -> dict:
    return {
        "message_scene": "group" if group else "friend",
        "peer_id": GROUP if group else USER,
        "message_seq": seq,
        "sender_id": USER,
        "time": 0,
        "segments": segments,
    }


def milky_event(segments: list[dict], group: bool = True, reply: Optional[dict] = None):
    cls = MilkyGME if group else MilkyFME
    return cls(
        time=0,
        self_id=SELF,
        data=milky_data(segments, group),
        reply=IncomingMessage(**reply) if reply else None,
    )


def text(s: str) -> dict:
    return {"type": "text", "data": {"text": s}}


MILKY_IMAGE = {
    "type": "image",
    "data": {
        "resource_id": "rid",
        "temp_url": "https://multimedia.nt.qq.com.cn/download?appid=1&rkey=x",
        "width": 1,
        "height": 1,
        "sub_type": "normal",
    },
}


def real_bot(adapter):
    import nonebot

    if adapter is MilkyAdapter:
        return MilkyBot(nonebot.get_adapter(MilkyAdapter), str(SELF), None)  # type: ignore
    return V11Bot(nonebot.get_adapter(V11Adapter), str(SELF))


# ---------- 作用域 ----------


def test_scope_group_same_for_both_adapters():
    from nonebot_plugin_savepic.adapter import get_scope

    # Milky 必须与 OneBot 产生同样的键，旧图片才能继续访问
    assert get_scope(v11_event()) == f"qq_group:{GROUP}"
    assert get_scope(milky_event([text("hi")])) == f"qq_group:{GROUP}"


def test_scope_private_is_globe():
    from nonebot_plugin_savepic.adapter import get_scope

    assert get_scope(v11_event(group=False)) == "globe"
    assert get_scope(milky_event([text("hi")], group=False)) == "globe"


def test_group_message_event_union():
    from nonebot_plugin_savepic.adapter import _GROUP_EVENTS

    assert V11GME in _GROUP_EVENTS
    assert MilkyGME in _GROUP_EVENTS


# ---------- 用户 ----------


def test_user_key_milky_maps_to_onebot():
    from nonebot_plugin_savepic.adapter import get_user_key

    assert get_user_key(real_bot(V11Adapter), v11_event()) == f"onebot:{USER}"
    assert (
        get_user_key(real_bot(MilkyAdapter), milky_event([text("hi")]))
        == f"onebot:{USER}"
    )


@pytest.mark.parametrize(
    "admins",
    [[f"onebot:{USER}"], [f"milky:{USER}"], [str(USER)]],
)
async def test_pic_admin_on_milky(monkeypatch: pytest.MonkeyPatch, admins):
    from nonebot_plugin_savepic.rule import PIC_ADMIN
    from nonebot_plugin_savepic.config import plugin_config

    monkeypatch.setattr(plugin_config, "savepic_admin", admins)
    assert await PIC_ADMIN(real_bot(MilkyAdapter), milky_event([text("hi")]))


async def test_pic_admin_rejects_other(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_savepic.rule import PIC_ADMIN
    from nonebot_plugin_savepic.config import plugin_config

    monkeypatch.setattr(plugin_config, "savepic_admin", ["onebot:1"])
    assert not await PIC_ADMIN(real_bot(MilkyAdapter), milky_event([text("hi")]))


# ---------- 引用与图片 ----------


def test_reply_id():
    from nonebot_plugin_savepic.adapter import get_reply_id

    reply = V11Reply(
        time=0,
        message_type="group",
        message_id=42,
        real_id=42,
        sender=Sender(user_id=USER),
        message=V11Msg(),
    )
    assert get_reply_id(v11_event(reply=reply)) == "42"
    assert get_reply_id(v11_event()) is None
    ev = milky_event([text("hi")], reply=milky_data([MILKY_IMAGE], seq=77))
    assert get_reply_id(ev) == "77"
    assert get_reply_id(milky_event([text("hi")])) is None


def test_pick_picture_from_milky_reply():
    from nonebot_plugin_savepic.adapter import pick_picture

    ev = milky_event([text("/simpic")], reply=milky_data([MILKY_IMAGE], seq=77))
    seg = pick_picture(MilkyMsg(), ev)
    assert seg is not None and seg.type == "image"
    assert seg.data["resource_id"] == "rid"


def test_pick_picture_market_face_from_milky_reply():
    from nonebot_plugin_savepic.adapter import pick_picture

    face = {
        "type": "market_face",
        "data": {
            "url": "https://example.com/face.gif",
            "emoji_package_id": 1,
            "emoji_id": "e",
            "key": "k",
            "summary": "s",
        },
    }
    ev = milky_event([text("/simpic")], reply=milky_data([face]))
    assert pick_picture(MilkyMsg(), ev).data["url"] == "https://example.com/face.gif"
    assert pick_picture(MilkyMsg(), ev, mface=False) is None


async def test_picture_url_milky():
    from nonebot_plugin_savepic.adapter import picture_url

    class Bot(MilkyBot):
        def __init__(self):
            pass

        async def get_resource_temp_url(self, resource_id: str) -> str:
            return f"https://fresh/{resource_id}"

    bot = Bot()
    seg = MilkyMsg.from_elements([MILKY_IMAGE])[0]
    # 有 temp_url 直接用，不走 OneBot 的 rkey
    assert await picture_url(bot, seg) == MILKY_IMAGE["data"]["temp_url"]
    seg.data.pop("temp_url")
    assert await picture_url(bot, seg) == "https://fresh/rid"


async def test_picture_url_onebot_without_nt_url():
    from nonebot_plugin_savepic.adapter import picture_url

    class Bot(V11Bot):
        def __init__(self):
            pass

    seg = V11Seg.image("https://example.com/a.jpg")
    assert await picture_url(Bot(), seg) == "https://example.com/a.jpg"


# ---------- 端到端：事件经过 matcher ----------


@pytest.mark.parametrize("adapter_name", ["milky", "onebot"])
async def test_countpic_scope(app: App, monkeypatch: pytest.MonkeyPatch, adapter_name):
    import nonebot
    from nonebot_plugin_savepic import command

    seen = []

    async def fake_countpic(reg, scope):
        seen.append(scope)
        return 3

    monkeypatch.setattr(command, "countpic", fake_countpic)

    async with app.test_matcher(command.cpic) as ctx:
        if adapter_name == "milky":
            adapter = nonebot.get_adapter(MilkyAdapter)
            bot = ctx.create_bot(
                base=MilkyBot, adapter=adapter, self_id=str(SELF), info=None
            )
            event = milky_event([text("/countpic")])
        else:
            adapter = nonebot.get_adapter(V11Adapter)
            bot = ctx.create_bot(base=V11Bot, adapter=adapter, self_id=str(SELF))
            event = v11_event("/countpic")
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, "共查找到 3 张图片。", result=None)

    assert seen == [f"qq_group:{GROUP}"]


async def test_listpic_forward_milky(app: App, monkeypatch: pytest.MonkeyPatch):
    import nonebot
    from nonebot_plugin_savepic import listpic
    from nonebot_plugin_savepic.config import plugin_config

    async def fake_listpic(reg, scope, pages=0):
        assert scope == f"qq_group:{GROUP}"
        return [("a.jpg", False), ("b.jpg", True)]

    monkeypatch.setattr(listpic, "listpic", fake_listpic)
    monkeypatch.setattr(plugin_config, "forward_when_listpic", True)
    monkeypatch.setattr(plugin_config, "count_per_page_in_list", 7)

    expected = MilkyMsg(
        MilkySeg.forward(
            [MilkySeg.node(USER, "Page 1", MilkyMsg("a.jpg ⭐\nb.jpg\n\nPage 1"))]
        )
    )

    async with app.test_matcher(listpic.s_listpic) as ctx:
        adapter = nonebot.get_adapter(MilkyAdapter)
        bot = ctx.create_bot(
            base=MilkyBot, adapter=adapter, self_id=str(SELF), info=None
        )
        event = milky_event([text("/listpic")])
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, expected, result=None)

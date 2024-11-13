import yaml
from openai import AsyncOpenAI

OPENAI_CONFIG = {}
try:
    with open("configs/chatgpt-vision/keys.yaml") as f:
        for i in yaml.safe_load(f):
            OPENAI_CONFIG[i.get("model")] = {
                "api_key": i.get("key"),
                "base_url": i.get("url"),
            }
except Exception:
    pass


async def error_chat(
    error: str,
    model: str = "gemini-1.5-flash",
    temperature: float = 0.2,
    **kwargs,
):
    if model not in OPENAI_CONFIG:
        raise ValueError(f"The model {model} is not supported.")
    try:
        rsp = await AsyncOpenAI(**OPENAI_CONFIG[model]).chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": f"```\n{error}\n```\n\n请为上面的报错生成一段大约15字的解释，将会直接提交给前台显示给用户，所以你不能包含任何代码，也不能涉及隐私消息。\n不需要在开头回复“好的”之类的，直接给出你生成的结果。",
                }
            ],
            model=model,
            temperature=temperature,
            **kwargs,
        )
        if not rsp:
            raise ValueError("The Response is Null.")
        if not rsp.choices:
            raise ValueError("The Choice is Null.")
        return rsp.choices[0].message.content
    except Exception as ex:
        return str(error)

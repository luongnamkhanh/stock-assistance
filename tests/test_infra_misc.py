"""Test infrastructure layer: TelegramBot + LlmClient."""
from src.adapters.gateways import LLM, Telegram
from src.infrastructure.llm import LlmClient
from src.infrastructure.telegram import TelegramBot


def run():
    assert issubclass(TelegramBot, Telegram) and issubclass(LlmClient, LLM)
    assert TelegramBot({}).broadcast("x") is False       # chua config -> im lang, khong crash
    import os
    saved = {k: os.environ.pop(k, None) for k in
             ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    try:
        try:
            LlmClient().complete("s", "u")
            assert False, "phai raise khi khong co key"
        except RuntimeError as e:
            assert "LLM key" in str(e)
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    print("test_infra_misc OK")


if __name__ == "__main__":
    run()

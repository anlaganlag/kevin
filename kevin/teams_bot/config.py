import os

from dotenv import load_dotenv

load_dotenv()


class BotConfig:
    PORT: int = int(os.getenv("PORT", "3978"))
    APP_ID: str = os.getenv("MICROSOFT_APP_ID", "")
    APP_PASSWORD: str = os.getenv("MICROSOFT_APP_PASSWORD", "")
    APP_TENANT_ID: str = os.getenv("MICROSOFT_APP_TENANT_ID", "")
    APP_TYPE: str = os.getenv("MICROSOFT_APP_TYPE", "SingleTenant")
    BOT_SECRET: str = os.getenv("TEAMS_BOT_SECRET", "")

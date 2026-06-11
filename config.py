# config.py
import os
from dataclasses import dataclass

import boto3


def load_env_file(path=".env"):
    """Load local .env values without overriding real environment variables."""
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def env_int(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


load_env_file()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME: str = os.getenv("BOT_USERNAME", "emosCheShiBox_bot")

    API_BASE_URL: str = os.getenv("API_BASE_URL", "https://emos.best/api")

    REDPACKET_CREATE_URL: str = f"{API_BASE_URL}/redPacket/create"
    REDPACKET_RECEIVE_URL: str = f"{API_BASE_URL}/redPacket/receive"

    LOTTERY_CREATE_URL: str = f"{API_BASE_URL}/lottery/create"
    LOTTERY_CANCEL_URL: str = f"{API_BASE_URL}/lottery/cancel"

    RANK_PLAYING_URL: str = f"{API_BASE_URL}/rank/userVideoRecordPlaying"
    RANK_CARROT_URL: str = f"{API_BASE_URL}/rank/carrot"
    RANK_UPLOAD_URL: str = f"{API_BASE_URL}/rank/upload"

    API_USER_ENDPOINT: str = os.getenv("API_USER_ENDPOINT", f"{API_BASE_URL}/user")

    R2_ACCESS_KEY: str = os.getenv("R2_ACCESS_KEY", "")
    R2_SECRET_KEY: str = os.getenv("R2_SECRET_KEY", "")
    R2_BUCKET_NAME: str = os.getenv("R2_BUCKET_NAME", "redpacket-images")
    R2_PUBLIC_URL: str = os.getenv("R2_PUBLIC_URL", "")
    R2_ENDPOINT: str = os.getenv("R2_ENDPOINT", "")


BOT_COMMANDS = [
    ("start", "开始登录"),
    ("playing", "正在播放"),
    ("rank_carrot", "萝卜榜"),
    ("redpocket", "创建红包"),
    ("check_redpacket", "查询红包"),
    ("gameshoot", "猜拳游戏"),
    ("createguess", "创建猜大小游戏"),
    ("guess_bet", "猜大小下注"),
    ("rob", "打劫游戏"),
    ("robstatus", "打劫状态"),
    ("cardduel", "扑克牌比大小"),
    ("niuniu", "牛牛游戏"),
    ("guess", "猜大小游戏"),
    ("slot", "老虎机游戏"),
    ("blackjack", "21点游戏"),
    ("balance", "查看余额"),
    ("withdraw", "提现"),
    ("rules", "游戏规则"),
    ("help", "帮助"),
]


GROUP_ALLOWED_COMMANDS = [
    "balance",
    "redpocket",
    "check_redpacket",
    "gameshoot",
    "createguess",
    "guess_bet",
    "rob",
    "robstatus",
    "cardduel",
    "niuniu",
    "guess",
    "slot",
    "blackjack",
    "rules",
]


user_tokens = {}

DEFAULT_GROUP_CHAT_ID = env_int("DEFAULT_GROUP_CHAT_ID", 0)


def get_user_token(user_id):
    user_info = user_tokens.get(user_id)
    if not user_info:
        return None
    if isinstance(user_info, dict):
        return user_info.get("token")
    return user_info


SERVICE_PROVIDER_TOKEN = os.getenv("SERVICE_PROVIDER_TOKEN", "")


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": env_int("DB_PORT", 3306),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "game_db_test"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4"),
    "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 3),
    "read_timeout": env_int("DB_READ_TIMEOUT", 3),
    "write_timeout": env_int("DB_WRITE_TIMEOUT", 3),
}


TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "")
HTTP_PROXY_URL = os.getenv("HTTP_PROXY_URL", TELEGRAM_PROXY)


def init_r2_client():
    if not (Config.R2_ENDPOINT and Config.R2_ACCESS_KEY and Config.R2_SECRET_KEY):
        print("R2 client skipped: missing R2 env configuration")
        return None

    try:
        from botocore.client import Config as BotoConfig

        boto_config = BotoConfig(signature_version="s3v4", connect_timeout=5, read_timeout=5)

        client = boto3.client(
            "s3",
            endpoint_url=Config.R2_ENDPOINT,
            aws_access_key_id=Config.R2_ACCESS_KEY,
            aws_secret_access_key=Config.R2_SECRET_KEY,
            config=boto_config,
            region_name="auto",
        )
        print("R2 client initialized")
        return client
    except Exception as e:
        print(f"R2 client init failed: {e}")
        return None


WITHDRAW_LIMITS = {
    "daily": 0,
    "monthly": 0,
    "lifetime": 0,
}


RECHARGE_LIMITS = {
    "daily": 0,
    "monthly": 0,
    "lifetime": env_int("RECHARGE_LIFETIME_LIMIT", 1000),
}

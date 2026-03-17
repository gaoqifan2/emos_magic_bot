# config.py
import os
from dataclasses import dataclass
import boto3

@dataclass
class Config:
    # 正式Bot配置
    BOT_TOKEN: str = "8682707944:AAGvauAZxz8BRxwFd2piaG3adi01zGQtydY"
    BOT_USERNAME: str = "emosMagicBox_bot"

    #测试bot
    # BOT_TOKEN: str = "8269931184:AAEUOExcBkipGwTxOFbeyw-JDdXlQzD2OXs"
    # BOT_USERNAME: str = "emosCeshi_bot"
    
    # API地址
    # 生产环境地址
    API_BASE_URL: str = "https://emos.best/api"
    # 测试环境地址
    # API_BASE_URL: str = "https://dev.emos.best/api"
    
    # 红包相关
    REDPACKET_CREATE_URL: str = f"{API_BASE_URL}/redPacket/create"
    REDPACKET_RECEIVE_URL: str = f"{API_BASE_URL}/redPacket/receive"
    
    # 抽奖相关
    LOTTERY_CREATE_URL: str = f"{API_BASE_URL}/lottery/create"
    LOTTERY_CANCEL_URL: str = f"{API_BASE_URL}/lottery/cancel"
    
    # 排行榜相关
    RANK_PLAYING_URL: str = f"{API_BASE_URL}/rank/userVideoRecordPlaying"
    RANK_CARROT_URL: str = f"{API_BASE_URL}/rank/carrot"
    RANK_UPLOAD_URL: str = f"{API_BASE_URL}/rank/upload"
    
    # Cloudflare R2配置
    R2_ACCESS_KEY: str = "6418f1afb056eaefe68b38294e9666a9"
    R2_SECRET_KEY: str = "9dfa529c359c8b1439c7564f0a41f03b35ae8b8b88cf59786cce43bb06e57035"
    R2_BUCKET_NAME: str = "redpacket-images"
    R2_PUBLIC_URL: str = "https://red.030518.xyz"
    R2_ENDPOINT: str = "https://41fcfa149618e3923fb20db2212713dd.r2.cloudflarestorage.com"

# 机器人命令菜单
BOT_COMMANDS = [
    ("start", "开始/登录"),
    ("playing", "正在播放"),
    ("rank_carrot", "萝卜榜"),
    ("redpocket", "创建红包"),
    ("lottery", "创建抽奖"),
    ("check_redpacket", "查询红包"),
    ("lottery_cancel", "取消抽奖"),
    ("rank_upload", "上传榜"),
    ("cancel", "取消操作"),
    ("help", "帮助")
]

# 全局变量 - 存储用户token
user_tokens = {}

# 服务商token（用于为所有用户创建支付订单）
SERVICE_PROVIDER_TOKEN = "1047_ow2NHeo3HyzDSxvl"

# MySQL数据库配置
DB_CONFIG = {
    "host": "23.148.20.15",
    "port": 3306,
    "user": "root",
    "password": "H_fans200109~",
    "database": "game_db",
    "charset": "utf8mb4"
}

# 初始化R2客户端
def init_r2_client():
    try:
        from botocore.client import Config as BotoConfig
        
        boto_config = BotoConfig(signature_version='s3v4')
        
        client = boto3.client(
            's3',
            endpoint_url=Config.R2_ENDPOINT,
            aws_access_key_id=Config.R2_ACCESS_KEY,
            aws_secret_access_key=Config.R2_SECRET_KEY,
            config=boto_config,
            region_name='auto'
        )
        # 测试连接
        client.list_objects_v2(Bucket=Config.R2_BUCKET_NAME, MaxKeys=1)
        print("✅ R2客户端初始化成功")
        return client
    except Exception as e:
        print(f"❌ R2客户端初始化失败: {e}")
        return None

# 全局R2客户端
# r2_client = init_r2_client()
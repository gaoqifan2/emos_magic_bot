# config.py
import os
from dataclasses import dataclass
import boto3

@dataclass
class Config:
    # Bot配置
    BOT_TOKEN: str = "8682707944:AAExhJTlXyryFaHdfu6ZgBsjiuOpX_9Jm-E"
    BOT_USERNAME: str = "emosMagicBox_bot"
    
    # API地址
    API_BASE_URL: str = "http://localhost:8000/api"
    
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
    R2_PUBLIC_URL: str = "https://pub-1c439b34c477a87f999a32576e8eb.r2.dev"
    R2_ENDPOINT: str = "https://41fcfa149618e3923fb20db2212713dd.r2.cloudflarestorage.com"

# 机器人命令菜单
BOT_COMMANDS = [
    ("start", "开始/登录"),
    ("menu", "打开功能菜单"),
    ("redpocket", "创建红包"),
    ("check_redpacket", "查询红包"),
    ("lottery", "创建抽奖"),
    ("lottery_cancel", "取消抽奖"),
    ("rank_carrot", "萝卜榜"),
    ("rank_upload", "上传榜"),
    ("playing", "正在播放"),
    ("cancel", "取消操作"),
    ("help", "帮助")
]

# 全局变量 - 存储用户token
user_tokens = {}

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
r2_client = None
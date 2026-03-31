# config.py
import os
from dataclasses import dataclass
import boto3

@dataclass
class Config:
    # # 正式Bot配置
    # BOT_TOKEN: str = "8682707944:AAGvauAZxz8BRxwFd2piaG3adi01zGQtydY"
    # BOT_USERNAME: str = "emosMagicBox_bot"

    # 测试bot
    BOT_TOKEN: str = "8714100893:AAFxkl8zL2bpdNzgEBJ9fIseNsAG8D-mSjI"
    BOT_USERNAME: str = "emosCheShiBox_bot"
    
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
    
    # 游戏相关
    API_USER_ENDPOINT: str = f"https://emos.best/api/user"
    
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
    ("rank_upload", "上传榜"),
    ("gameshoot", "猜拳游戏"),
    ("slot", "老虎机游戏"),
    ("blackjack", "21点游戏"),
    ("balance", "查看余额"),
    ("guess", "猜大小游戏"),
    ("createguess", "创建群聊猜大小游戏"),
    ("guess_bet", "群聊猜大小下注"),
    ("withdraw", "提现"),
    ("help", "帮助"),
]

# 群聊中允许的命令列表
# 空列表表示群聊中不允许任何命令
GROUP_ALLOWED_COMMANDS = [
    "balance",     # 查看余额
    "guess", 
    "slot",  
    "blackjack",      # 21点游戏    
    "createguess",   # 创建猜大小游戏
    "guess_bet",         # 群聊下注
    "gameshoot",   # 猜拳游戏
]

# 全局变量 - 存储用户token
user_tokens = {}

# 默认群聊ID（用于设置群标签）
# 旧群ID（测试群）
# DEFAULT_GROUP_CHAT_ID = -1003833383798
# 新群ID（正式群）
DEFAULT_GROUP_CHAT_ID = -1003750565627  # 用户提供的正式群聊ID

def get_user_token(user_id):
    """从user_tokens中获取用户的token字符串
    
    支持两种存储格式：
    1. 字典格式: {'token': 'xxx', 'user_id': 'xxx', ...}
    2. 字符串格式: 'xxx'
    
    Args:
        user_id: 用户ID
        
    Returns:
        token字符串或None
    """
    user_info = user_tokens.get(user_id)
    if not user_info:
        return None
    
    # 如果是字典，提取token字段
    if isinstance(user_info, dict):
        return user_info.get('token')
    
    # 如果是字符串，直接返回
    return user_info

# 服务商token（用于为所有用户创建支付订单）
SERVICE_PROVIDER_TOKEN = "1047_ow2NHeo3HyzDSxvl"

# MySQL数据库配置（正式环境）
DB_CONFIG = {
    #测试数据库
    "host": "66.235.105.125",
    "port": 3306,
    "user": "root",
    "password": "H_fans200109~",
    "database": "game_db_test",
    "charset": "utf8mb4"


    # #正式数据库
    # "host": "66.235.105.125",
    # "port": 3306,
    # "user": "root",
    # "password": "H_fans200109~",
    # "database": "game_db",
    # "charset": "utf8mb4"
}

# 提现限制配置
WITHDRAW_LIMITS = {
    "daily": 50,  # 每日提现上限（萝卜）
    "monthly": 200,  # 每月提现上限（萝卜）
    "lifetime": 1000  # 终身提现上限（萝卜）
}

# 充值限制配置
RECHARGE_LIMITS = {
    "daily": 100,  # 每日充值上限（萝卜）
    "monthly": 500  # 每月充值上限（萝卜）
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
# utils/r2_client.py
import logging
import uuid
import boto3
from botocore.client import Config as BotoConfig

from config import Config as AppConfig
from utils.http_client import http_client

logger = logging.getLogger(__name__)

class R2Client:
    """Cloudflare R2 存储客户端"""
    
    def __init__(self):
        self.client = None
        self.bucket = AppConfig.R2_BUCKET_NAME
        self.public_url = AppConfig.R2_PUBLIC_URL
        self._init_client()
    
    def _init_client(self):
        """初始化R2客户端"""
        try:
            boto_config = BotoConfig(signature_version='s3v4', connect_timeout=5, read_timeout=5)
            self.client = boto3.client(
                's3',
                endpoint_url=AppConfig.R2_ENDPOINT,
                aws_access_key_id=AppConfig.R2_ACCESS_KEY,
                aws_secret_access_key=AppConfig.R2_SECRET_KEY,
                config=boto_config,
                region_name='auto'
            )
            # 移除测试连接，避免超时问题
            # self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
            logger.info("✅ R2客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ R2客户端初始化失败: {e}")
            self.client = None
    
    def upload_file(self, file_data: bytes, file_name: str = None, folder: str = "uploads") -> str:
        """上传文件到R2
        
        Args:
            file_data: 文件二进制数据
            file_name: 文件名（可选）
            folder: 存储文件夹
            
        Returns:
            文件的公网访问URL
        """
        if not self.client:
            raise Exception("R2客户端未初始化")
        
        # 生成唯一文件名
        if file_name and '.' in file_name:
            ext = file_name.split('.')[-1].lower()
        else:
            ext = 'jpg'
        
        # 确保扩展名有效
        valid_exts = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'ogg', 'mp3', 'wav', 'm4a', 'aac', 'flac', 'opus', 'webm']
        if ext not in valid_exts:
            ext = 'jpg'
        
        key = f"{folder}/{uuid.uuid4()}.{ext}"
        
        try:
            # 根据扩展名设置Content-Type
            content_type = 'image/jpeg'
            if ext == 'png':
                content_type = 'image/png'
            elif ext == 'gif':
                content_type = 'image/gif'
            elif ext == 'webp':
                content_type = 'image/webp'
            elif ext == 'bmp':
                content_type = 'image/bmp'
            elif ext == 'ogg':
                content_type = 'audio/ogg'
            elif ext == 'mp3':
                content_type = 'audio/mpeg'
            elif ext == 'wav':
                content_type = 'audio/wav'
            elif ext == 'm4a':
                content_type = 'audio/mp4'
            elif ext == 'aac':
                content_type = 'audio/aac'
            elif ext == 'flac':
                content_type = 'audio/flac'
            elif ext == 'opus':
                content_type = 'audio/opus'
            elif ext == 'webm':
                content_type = 'audio/webm'
            
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_data,
                ContentType=content_type
            )
            
            url = f"{self.public_url}/{key}"
            logger.info(f"✅ 文件上传成功: {url}")
            return url
            
        except Exception as e:
            logger.error(f"❌ 上传文件失败: {e}")
            raise

# 全局R2客户端实例
r2_client = R2Client()
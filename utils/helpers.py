# utils/helpers.py
import os
import json
from datetime import datetime

def format_size(bytes_num: int) -> str:
    """格式化字节大小为易读格式"""
    if bytes_num < 1024:
        return f"{bytes_num} B"
    elif bytes_num < 1024 * 1024:
        return f"{bytes_num/1024:.2f} KB"
    elif bytes_num < 1024 * 1024 * 1024:
        return f"{bytes_num/(1024*1024):.2f} MB"
    elif bytes_num < 1024 * 1024 * 1024 * 1024:
        return f"{bytes_num/(1024*1024*1024):.2f} GB"
    else:
        return f"{bytes_num/(1024*1024*1024*1024):.2f} TB"

def format_datetime(dt_str: str) -> str:
    """格式化日期时间字符串"""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return dt_str

def safe_json_loads(text: str, default=None):
    """安全解析JSON"""
    try:
        return json.loads(text)
    except:
        return default if default is not None else {}

def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def ensure_dir(path: str):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)

def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''

def is_image_file(filename: str) -> bool:
    """判断是否为图片文件"""
    ext = get_file_extension(filename)
    return ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']

def is_video_file(filename: str) -> bool:
    """判断是否为视频文件"""
    ext = get_file_extension(filename)
    return ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm']

def format_number(num: int) -> str:
    """格式化数字（加千位分隔符）"""
    return f"{num:,}"

def parse_command_args(text: str):
    """解析命令参数"""
    if not text:
        return []
    parts = text.strip().split()
    return parts[1:] if len(parts) > 1 else []
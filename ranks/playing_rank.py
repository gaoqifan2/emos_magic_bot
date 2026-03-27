# ranks/playing_rank.py
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config
from utils.message_utils import auto_delete_message
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

def safe_str(value, default=""):
    """安全地转换值为字符串"""
    if value is None:
        return default
    return str(value)

def safe_int(value, default=0):
    """安全地转换值为整数"""
    if value is None:
        return default
    try:
        return int(value)
    except:
        return default

def to_unicode(text):
    """将文本转换为Unicode格式"""
    if text is None:
        return ""
    return str(text)

async def playing_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """正在播放排行榜 - 修复Markdown格式"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    if update.callback_query:
        await update.callback_query.answer()
    
    if update.callback_query:
        loading = await update.callback_query.edit_message_text("🔄 正在获取播放排行榜...")
    else:
        loading = await update.message.reply_text("🔄 正在获取播放排行榜...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            Config.RANK_PLAYING_URL,
            headers=headers,
            timeout=10
        )
        
        # 确保使用正确的编码
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            data = response.json()
            
            if not data:
                await loading.edit_text("🎬 正在播放排行榜\n\n暂无数据")
                return
            
            # 按视频标题分组
            videos = {}
            for item in data:
                video_title = to_unicode(item.get('video_title', '未知视频'))
                uploader = to_unicode(item.get('upload_pseudonym', 'emos'))
                
                video_key = f"{video_title}|{uploader}"
                if video_key not in videos:
                    videos[video_key] = {
                        'title': video_title,
                        'uploader': uploader,
                        'users': []
                    }
                
                username = to_unicode(item.get('username', '未知用户'))
                season = safe_int(item.get('season_number'), 1)
                episode = safe_int(item.get('episode_number'), 1)
                play_seconds = safe_int(item.get('play_seconds'), 0)
                play_speed = safe_int(item.get('play_speed'), 10)
                
                minutes = play_seconds // 60
                seconds = play_seconds % 60
                progress = f"{minutes:02d}:{seconds:02d}"
                speed = f"{play_speed/10:.1f}x"
                
                videos[video_key]['users'].append({
                    'username': username,
                    'episode': f"S{season:02d}E{episode:02d}",
                    'progress': progress,
                    'speed': speed
                })
            
            # 构建消息 - 不使用 Markdown，直接用普通文本
            message = "🎬 正在播放排行榜\n\n"
            video_count = 0
            
            for video in videos.values():
                # 视频标题不加粗，直接显示
                message += f"{video['title']}\n"
                message += f"上传者: {video['uploader']}\n"
                
                for user in video['users']:
                    message += f"— {user['username']} 在看 {user['episode']} {user['progress']} {user['speed']}\n"
                
                message += "\n"
                video_count += 1
            
            message += f"总计 {video_count} 个视频正在播放"
            
            keyboard = [
                [InlineKeyboardButton("🔙 返回排行榜菜单", callback_data="menu_rank_main")],
                [InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 移除 parse_mode="Markdown"，使用纯文本
            await loading.edit_text(message, reply_markup=reply_markup)
            # 30秒后自动消失
            asyncio.create_task(auto_delete_message(update, context, None, 30))
        else:
            await loading.edit_text(f"❌ 获取失败，状态码：{response.status_code}")
            
    except Exception as e:
        logger.error(f"获取播放排行榜失败: {e}")
        await loading.edit_text(f"❌ 获取失败：{str(e)}")
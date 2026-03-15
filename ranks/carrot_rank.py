# ranks/carrot_rank.py
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

def format_number(num):
    """格式化数字，添加千位分隔符"""
    return f"{num:,}"

def to_unicode(text):
    """将文本转换为Unicode格式"""
    if text is None:
        return ""
    return str(text)

async def rank_carrot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """萝卜排行榜 - 左右分列版"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    if update.callback_query:
        await update.callback_query.answer()
    
    if update.callback_query:
        loading = await update.callback_query.edit_message_text("🔄 正在获取萝卜排行榜...")
    else:
        loading = await update.message.reply_text("🔄 正在获取萝卜排行榜...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            Config.RANK_CARROT_URL,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if not data:
                await loading.edit_text("🏆 萝卜排行榜\n\n暂无数据")
                return
            
            message = "🏆 萝卜排行榜 (前30)\n\n"
            message += "```\n"
            
            left_column = []
            right_column = []
            
            for i, item in enumerate(data[:30], 1):
                username = to_unicode(item.get('username', '未知用户'))
                carrot = item.get('carrot', 0)
                carrot_str = format_number(carrot)
                
                if len(username) > 12:
                    username = username[:10] + ".."
                
                left_column.append(f"{i}. {username}")
                right_column.append(carrot_str)
            
            max_left_width = max(len(line) for line in left_column)
            
            for left, right in zip(left_column, right_column):
                message += f"{left:<{max_left_width}}  {right:>8}\n"
            
            message += "```"
            
            keyboard = [
                [InlineKeyboardButton("🔙 返回排行榜菜单", callback_data="menu_rank_main")],
                [InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await loading.edit_text(f"❌ 获取失败，状态码：{response.status_code}")
            
    except Exception as e:
        logger.error(f"获取萝卜排行榜失败: {e}")
        await loading.edit_text(f"❌ 获取失败：{str(e)}")
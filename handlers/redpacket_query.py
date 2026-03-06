# handlers/redpacket_query.py
import logging
import requests
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import user_tokens, Config
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

# 对话状态
WAITING_REDPACKET_ID = 20

async def check_redpacket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """查询红包记录"""
    user_id = update.effective_user.id
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return ConversationHandler.END
    
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "📊 查询红包领取记录\n\n"
            "请输入红包ID：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "📊 查询红包领取记录\n\n"
            "请输入红包ID：",
            reply_markup=reply_markup
        )
    return WAITING_REDPACKET_ID

async def get_redpacket_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收红包ID并查询记录"""
    user_id = update.effective_user.id
    redpacket_id = update.message.text.strip()
    token = user_tokens.get(user_id)
    
    logger.info(f"用户 {user_id} 查询红包: {redpacket_id}")
    
    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    loading_msg = await update.message.reply_text("🔄 正在查询红包记录...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{Config.REDPACKET_RECEIVE_URL}?red_packet_id={redpacket_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if not data or not data.get('items'):
                await loading_msg.edit_text(
                    f"📊 红包查询结果\n\n"
                    f"红包ID: {redpacket_id}\n"
                    f"暂无领取记录"
                )
                return ConversationHandler.END
            
            message = f"📊 红包领取记录\n\n"
            message += f"红包ID: {redpacket_id}\n"
            message += f"总领取: {data.get('total', 0)} 人\n"
            message += f"当前页: {data.get('page', 1)}/{ (data.get('total', 0) + data.get('page_size', 15) - 1) // data.get('page_size', 15)}\n\n"
            
            for item in data.get('items', []):
                username = item.get('username', '未知用户')
                carrot = item.get('carrot', 0)
                receive_at = item.get('receive_at', '未知时间')[:19].replace('T', ' ')
                message += f"👤 {username}\n   🥕 {carrot} 萝卜\n   ⏰ {receive_at}\n\n"
                
                if len(message) > 3500:
                    await update.message.reply_text(message)
                    message = ""
            
            if message:
                await loading_msg.edit_text(message)
            else:
                await loading_msg.delete()
                
        elif response.status_code == 401:
            if user_id in user_tokens:
                del user_tokens[user_id]
            await loading_msg.edit_text("❌ 登录已过期，请重新发送 /start 登录")
        elif response.status_code == 404:
            await loading_msg.edit_text(f"❌ 未找到红包ID: {redpacket_id}")
        else:
            await loading_msg.edit_text(f"❌ 查询失败，状态码：{response.status_code}")
            
    except Exception as e:
        logger.error(f"用户 {user_id} 红包查询失败: {e}")
        await loading_msg.edit_text("❌ 查询失败，请稍后重试")
    
    return ConversationHandler.END
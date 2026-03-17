# games/lottery_cancel.py
import logging
import requests
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import user_tokens, Config
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

WAITING_LOTTERY_CANCEL_ID = 21

async def lottery_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消抽奖"""
    user_id = update.effective_user.id
    
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录", reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录", reply_markup=reply_markup)
        return ConversationHandler.END
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🎲 取消抽奖\n\n"
            "请输入要取消的抽奖ID：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🎲 取消抽奖\n\n"
            "请输入要取消的抽奖ID：",
            reply_markup=reply_markup
        )
    return WAITING_LOTTERY_CANCEL_ID

async def get_lottery_cancel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收抽奖ID并取消"""
    user_id = update.effective_user.id
    lottery_id = update.message.text.strip()
    token = user_tokens.get(user_id)
    
    logger.info(f"用户 {user_id} 请求取消抽奖: {lottery_id}")
    
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录", reply_markup=reply_markup)
        return ConversationHandler.END
    
    loading_msg = await update.message.reply_text("🔄 正在取消抽奖...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.put(
            f"{Config.LOTTERY_CANCEL_URL}?lottery_id={lottery_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("is_success"):
                await loading_msg.edit_text(
                    f"✅ 抽奖取消成功！\n\n"
                    f"抽奖ID: {lottery_id}"
                )
            else:
                await loading_msg.edit_text(f"❌ 取消失败：操作未成功")
        elif response.status_code == 401:
            if user_id in user_tokens:
                del user_tokens[user_id]
            await loading_msg.edit_text("❌ 登录已过期，请重新发送 /start 登录")
        elif response.status_code == 404:
            await loading_msg.edit_text(f"❌ 未找到抽奖ID: {lottery_id}")
        else:
            await loading_msg.edit_text(f"❌ 取消失败，状态码：{response.status_code}")
            
    except Exception as e:
        logger.error(f"用户 {user_id} 取消抽奖失败: {e}")
        await loading_msg.edit_text("❌ 取消失败，请稍后重试")
    
    # 操作完成后显示返回菜单按钮
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏠 返回菜单", reply_markup=reply_markup)
    
    return ConversationHandler.END
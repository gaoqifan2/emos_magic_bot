# handlers/redpacket_query.py
import logging
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from config import user_tokens, Config
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

WAITING_REDPACKET_ID, WAITING_QUERY_TYPE = range(20, 22)

async def check_redpacket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """查询红包记录"""
    user_id = update.effective_user.id
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return ConversationHandler.END
    
    # 显示查询类型选择
    keyboard = [
        [InlineKeyboardButton("📋 查看我发的红包", callback_data="my_redpackets")],
        [InlineKeyboardButton("🔍 输入红包ID查询", callback_data="input_id")]
    ]
    keyboard = add_cancel_button(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "📊 查询红包记录\n\n请选择查询方式：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "📊 查询红包记录\n\n请选择查询方式：",
            reply_markup=reply_markup
        )
    return WAITING_QUERY_TYPE

async def handle_query_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理查询类型选择"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "my_redpackets":
        # 查看我发的红包
        token = user_tokens.get(user_id)
        if not token:
            await query.edit_message_text("❌ 登录已过期，请重新发送 /start 登录")
            return ConversationHandler.END
        
        loading = await query.edit_message_text("🔄 正在查询您发的红包...")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(
                f"{Config.API_BASE_URL}/redPacket/my",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not data or not data.get('items'):
                    await loading.edit_text("📊 您还没有发过红包")
                    return ConversationHandler.END
                
                message = "📋 我发的红包\n\n"
                
                for item in data.get('items', [])[:10]:  # 最多显示10个
                    red_packet_id = item.get('red_packet_id', '未知')
                    carrot = item.get('carrot', 0)
                    number = item.get('number', 0)
                    received = item.get('received', 0)
                    status = item.get('status', 'unknown')
                    created_at = item.get('created_at', '未知时间')[:19].replace('T', ' ')
                    
                    status_display = "✅ 已领取" if status == "completed" else "🔄 进行中"
                    
                    message += f"🆔 红包ID: `{red_packet_id}`\n"
                    message += f"💰 金额: {carrot} 萝卜\n"
                    message += f"👥 人数: {received}/{number}\n"
                    message += f"📅 时间: {created_at}\n"
                    message += f"📊 状态: {status_display}\n\n"
                
                await loading.edit_text(message, parse_mode="Markdown")
            else:
                await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}")
                if response.text:
                    logger.error(f"API返回: {response.text}")
            
        except Exception as e:
            logger.error(f"查询我的红包失败: {e}")
            await loading.edit_text("❌ 查询失败，请稍后重试")
        
        return ConversationHandler.END
    
    elif data == "input_id":
        # 输入红包ID查询
        keyboard = add_cancel_button([[]])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 查询红包领取记录\n\n请输入红包ID：",
            reply_markup=reply_markup
        )
        return WAITING_REDPACKET_ID
    
    return ConversationHandler.END

async def get_redpacket_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收红包ID并查询记录"""
    user_id = update.effective_user.id
    redpacket_id = update.message.text.strip()
    token = user_tokens.get(user_id)
    
    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    loading = await update.message.reply_text("🔄 正在查询红包记录...")
    
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
                await loading.edit_text(f"📊 红包查询结果\n\n红包ID: {redpacket_id}\n暂无领取记录")
                return ConversationHandler.END
            
            message = f"📊 红包领取记录\n\n红包ID: {redpacket_id}\n"
            message += f"总领取: {data.get('total', 0)} 人\n\n"
            
            for item in data.get('items', []):
                username = item.get('username', '未知用户')
                carrot = item.get('carrot', 0)
                receive_at = item.get('receive_at', '未知时间')[:19].replace('T', ' ')
                message += f"👤 {username}\n   🥕 {carrot} 萝卜\n   ⏰ {receive_at}\n\n"
            
            await loading.edit_text(message)
        else:
            await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}")
            
    except Exception as e:
        logger.error(f"查询红包失败: {e}")
        await loading.edit_text("❌ 查询失败，请稍后重试")
    
    return ConversationHandler.END